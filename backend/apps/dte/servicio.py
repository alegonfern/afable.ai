"""Lo que hace el facturador por cada empresa: cargar su certificado y sus folios, decir qué le
falta para emitir y emitir (folio, timbre, firma, envío). La conversación con el SII después de
emitir (subir, consultar) es del motor (motor.py), que corre en segundo plano.
"""
import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Caf, CertificadoDigital, ConfiguracionDTE, DocumentoEmitido, EnvioSII
from .nucleo import ErrorDTE, documento, envio
from .nucleo import rut as ruts
from .nucleo.caf import Caf as CafNucleo
from .nucleo.certificado import Certificado
from .sii import CERTIFICACION, PRODUCCION

TIPOS_SOPORTADOS = sorted(documento.TIPOS)
DIAS_AVISO_CERTIFICADO = 30
FOLIOS_AVISO = 20


def disponible(org):
    """Si la empresa ve el facturador nativo. Apagado para todos hasta probarlo entero:
    DTE_NATIVO = 'off' | 'piloto' (solo las empresas de DTE_PILOTO) | 'on'."""
    modo = getattr(settings, 'DTE_NATIVO', 'off')
    if modo == 'on':
        return True
    return modo == 'piloto' and getattr(org, 'slug', None) in getattr(settings, 'DTE_PILOTO', [])


def certificado_activo(org):
    return CertificadoDigital.objects.filter(organization=org, activo=True).first()


# ── Carga de certificado y folios ─────────────────────────────────────────────────────────

def cargar_certificado(org, datos, clave, usuario=None):
    cert = Certificado.desde_pfx(datos, clave)
    if not cert.rut:
        raise ErrorDTE('El certificado no trae el RUT de su titular. Use un certificado digital emitido en Chile '
                       'para personas (e-certchile, Acepta, E-Sign...).')
    if not cert.vigente():
        raise ErrorDTE(f'El certificado venció el {timezone.localtime(cert.valido_hasta):%d-%m-%Y}.')
    from cryptography.hazmat.primitives import serialization
    huella = hashlib.sha256(cert.cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    with transaction.atomic():
        CertificadoDigital.objects.filter(organization=org, activo=True).update(activo=False)
        modelo = CertificadoDigital(organization=org, titular_nombre=cert.nombre[:200], titular_rut=cert.rut,
                                    emitido_por=cert.emisor[:200], valido_desde=cert.valido_desde,
                                    valido_hasta=cert.valido_hasta, huella=huella, subido_por=usuario)
        modelo.guardar_secretos(datos, clave)
        modelo.save()
    return modelo


def cargar_caf(org, datos, usuario=None, primer_folio=None):
    """Guarda un CAF. `primer_folio` sirve si parte del rango ya se usó en otro sistema."""
    caf = CafNucleo(datos)
    rut_empresa = ruts.normalizar(org.rut) if org.rut else None
    if rut_empresa != caf.rut:
        raise ErrorDTE(f'Ese CAF es del RUT {caf.rut} y la empresa es {rut_empresa or "sin RUT"}.')
    if caf.tipo not in documento.TIPOS:
        raise ErrorDTE(f'Afable todavía no emite documentos tipo {caf.tipo}.')
    ambiente = CERTIFICACION if caf.certificacion else PRODUCCION
    siguiente = caf.desde
    if primer_folio:
        if not caf.contiene(primer_folio):
            raise ErrorDTE(f'El folio {primer_folio} no está en el CAF (del {caf.desde} al {caf.hasta}).')
        siguiente = int(primer_folio)
    choca = Caf.objects.filter(organization=org, ambiente=ambiente, tipo=caf.tipo, desde__lte=caf.hasta,
                               hasta__gte=caf.desde).first()
    if choca:
        raise ErrorDTE(f'Ya hay un CAF de tipo {caf.tipo} con folios del {choca.desde} al {choca.hasta} '
                       'que se cruza con este.')
    usados = DocumentoEmitido.objects.filter(organization=org, ambiente=ambiente, tipo=caf.tipo,
                                             folio__gte=siguiente, folio__lte=caf.hasta)
    if usados.exists():
        raise ErrorDTE('Afable ya emitió folios de ese rango. Indique desde qué folio seguir.')
    modelo = Caf(organization=org, ambiente=ambiente, tipo=caf.tipo, desde=caf.desde, hasta=caf.hasta,
                 siguiente=siguiente, fecha_autorizacion=caf.fecha_autorizacion, subido_por=usuario)
    modelo.guardar_xml(caf.xml)
    modelo.save()
    return modelo


def folios(org, ambiente):
    """{tipo: folios disponibles} en ese ambiente."""
    total = {}
    for c in Caf.objects.filter(organization=org, ambiente=ambiente, siguiente__lte=F('hasta')):
        total[c.tipo] = total.get(c.tipo, 0) + c.disponibles
    return total


# ── Qué le falta a la empresa ─────────────────────────────────────────────────────────────

def emisor(org):
    from apps.comercial.models import ConfiguracionComercial
    e = ConfiguracionComercial.de(org).emisor
    cfg = ConfiguracionDTE.de(org)
    return documento.Emisor(rut=e['rut'] or '', razon_social=e['razon_social'] or '', giro=e['giro'] or '',
                            actecos=list(cfg.actecos or []), direccion=e['direccion'] or '', comuna=e['comuna'] or '',
                            ciudad=e['ciudad'] or '', telefono=cfg.telefono, correo=cfg.correo_emisor,
                            sucursal=cfg.sucursal, codigo_sucursal=cfg.codigo_sucursal)


def estado(org, ambiente=None):
    """Los pasos del alta, cada uno con si está listo y qué falta, y los avisos vigentes.
    Es lo que muestra el asistente en Ajustes › Empresas › Facturación electrónica."""
    from apps.comercial.models import ConfiguracionComercial
    cfg = ConfiguracionDTE.de(org)
    ambiente = ambiente or cfg.ambiente or CERTIFICACION
    cc = ConfiguracionComercial.de(org)
    faltan_empresa = list(cc.emisor_faltan)
    if org.rut and not ruts.valido(org.rut):
        faltan_empresa.append('un RUT válido')
    if not cfg.actecos:
        faltan_empresa.append('la actividad económica (código del SII)')
    cert = certificado_activo(org)
    ahora = timezone.now()
    disponibles = folios(org, ambiente)
    fecha_res, numero_res = cfg.resolucion(ambiente)

    pasos = [
        {'clave': 'empresa', 'titulo': 'Datos de la empresa', 'listo': not faltan_empresa,
         'falta': faltan_empresa},
        {'clave': 'camino', 'titulo': '¿Ya emite facturas electrónicas?', 'listo': bool(cfg.camino),
         'falta': [] if cfg.camino else ['indicar si ya emite con otro sistema o si debe certificarse']},
        {'clave': 'certificado', 'titulo': 'Certificado digital', 'listo': bool(cert and cert.valido_hasta > ahora),
         'falta': [] if cert and cert.valido_hasta > ahora else
                  ['subir el certificado digital (.pfx) de quien firma' if not cert else 'subir un certificado vigente']},
        {'clave': 'folios', 'titulo': 'Folios (CAF)', 'listo': disponibles.get(documento.FACTURA, 0) > 0,
         'falta': [] if disponibles.get(documento.FACTURA, 0) else
                  ['subir un CAF de facturas (33) ' + ('del ambiente de certificación' if ambiente == CERTIFICACION
                                                       else 'de producción')]},
        {'clave': 'resolucion', 'titulo': 'Autorización del SII', 'listo': bool(fecha_res) and numero_res is not None,
         'falta': [] if fecha_res and numero_res is not None else
                  (['la fecha de resolución que publica el SII en el ambiente de certificación']
                   if ambiente == CERTIFICACION else ['el número y la fecha de la resolución que autoriza a la empresa'])},
    ]
    avisos = []
    if cert and cert.valido_hasta > ahora and cert.valido_hasta - ahora < timedelta(days=DIAS_AVISO_CERTIFICADO):
        avisos.append(f'El certificado de {cert.titular_nombre} vence el {timezone.localtime(cert.valido_hasta):%d-%m-%Y}.')
    for tipo, n in sorted(disponibles.items()):
        if n < FOLIOS_AVISO:
            avisos.append(f'Quedan {n} folios de {documento.TIPOS[tipo].lower()}.')
    return {
        'disponible': disponible(org), 'ambiente': cfg.ambiente, 'ambiente_revisado': ambiente,
        'activo': cfg.activo, 'camino': cfg.camino, 'pasos': pasos,
        'listo': all(p['listo'] for p in pasos), 'avisos': avisos,
        'folios': [{'tipo': t, 'nombre': documento.TIPOS[t], 'disponibles': disponibles.get(t, 0)}
                   for t in TIPOS_SOPORTADOS],
        'certificado': {'titular': cert.titular_nombre, 'rut': cert.titular_rut, 'emitido_por': cert.emitido_por,
                        'vence': cert.valido_hasta.isoformat()} if cert else None,
    }


def faltantes(org, tipo, ambiente):
    e = estado(org, ambiente)
    falta = [f for p in e['pasos'] if p['clave'] != 'folios' for f in p['falta']]
    if not folios(org, ambiente).get(tipo):
        falta.append(f'folios de {documento.TIPOS.get(tipo, tipo).lower()}')
    return falta


# ── Encender y apagar ─────────────────────────────────────────────────────────────────────

def activar(org, ambiente, usuario=None):
    """Ventas pasa a emitir con este facturador, en el ambiente indicado."""
    from apps.comercial.models import ConfiguracionComercial
    if not disponible(org):
        raise ErrorDTE('El facturador electrónico de Afable todavía no está habilitado para esta empresa.')
    if ambiente not in (CERTIFICACION, PRODUCCION):
        raise ErrorDTE('Ambiente no válido.')
    e = estado(org, ambiente)
    if not e['listo']:
        falta = [f for p in e['pasos'] for f in p['falta']]
        raise ErrorDTE('Para activar falta: ' + '; '.join(falta) + '.')
    cfg = ConfiguracionDTE.de(org)
    cfg.ambiente, cfg.activo = ambiente, True
    cfg.activado_en, cfg.activado_por = timezone.now(), usuario
    cfg.save()
    cc = ConfiguracionComercial.de(org)
    cc.proveedor_dte = 'sii'
    cc.save(update_fields=['proveedor_dte'])
    return cfg


def desactivar(org):
    from apps.comercial.models import ConfiguracionComercial
    cfg = ConfiguracionDTE.de(org)
    cfg.activo = False
    cfg.save(update_fields=['activo', 'actualizado_en'])
    cc = ConfiguracionComercial.de(org)
    if cc.proveedor_dte == 'sii':
        cc.proveedor_dte = ''
        cc.save(update_fields=['proveedor_dte'])
    return cfg


# ── Emitir ────────────────────────────────────────────────────────────────────────────────

def _tomar_folio(org, ambiente, tipo):
    caf = (Caf.objects.select_for_update()
           .filter(organization=org, ambiente=ambiente, tipo=tipo, siguiente__lte=F('hasta'))
           .order_by('desde').first())
    if caf is None:
        raise ErrorDTE(f'No quedan folios de {documento.TIPOS.get(tipo, tipo).lower()}. Suba un CAF nuevo '
                       'en Ajustes › Empresas › Facturación electrónica.')
    folio = caf.siguiente
    caf.siguiente = folio + 1
    caf.save(update_fields=['siguiente'])
    return caf, folio


def emitir(org, doc, usuario=None, ambiente=None, subir=True):
    """Emite `doc` (nucleo.documento.Documento, sin folio): toma el folio, timbra, firma y deja el
    envío listo para el SII. Si algo falla antes de guardar, el folio no se gasta (todo es una
    transacción). La subida al SII ocurre después, fuera de la transacción."""
    cfg = ConfiguracionDTE.de(org)
    ambiente = ambiente or cfg.ambiente
    if not ambiente:
        raise ErrorDTE('La facturación electrónica de la empresa no está activada.')
    falta = faltantes(org, doc.tipo, ambiente)
    if falta:
        raise ErrorDTE('Para emitir falta: ' + '; '.join(falta) + '.')
    cert_modelo = certificado_activo(org)
    cert = cert_modelo.cargar()
    fecha_res, numero_res = cfg.resolucion(ambiente)
    momento = timezone.localtime().replace(tzinfo=None, microsecond=0)

    with transaction.atomic():
        caf, doc.folio = _tomar_folio(org, ambiente, doc.tipo)
        dte = documento.construir(doc, caf.cargar(), momento)
        t = documento.totales(doc)
        datos = envio.armar([dte], envio.Caratula(rut_emisor=doc.emisor.rut, rut_envia=cert.rut,
                                                  fecha_resolucion=fecha_res, numero_resolucion=numero_res),
                            cert, momento)
        e = EnvioSII.objects.create(organization=org, ambiente=ambiente, xml=datos.decode('iso-8859-1'),
                                    siguiente_intento=timezone.now())
        emitido = DocumentoEmitido.objects.create(
            organization=org, ambiente=ambiente, tipo=doc.tipo, folio=doc.folio, fecha=doc.fecha,
            receptor_rut=doc.receptor.rut, receptor_razon_social=doc.receptor.razon_social[:255],
            monto_neto=t.neto, monto_exento=t.exento, monto_iva=t.iva, monto_total=t.total,
            xml=envio.dte_suelto(envio.dtes_de(datos)[0]).decode('iso-8859-1'), envio=e, emitido_por=usuario)
        if subir:
            from . import motor
            transaction.on_commit(lambda: motor.subir_sin_fallar(e.id))
    return emitido


# ── Notas de crédito y débito ─────────────────────────────────────────────────────────────

def emitir_nota(org, original, tipo, codigo, razon, lineas=None, usuario=None):
    """Nota de crédito (61) o débito (56) sobre un DTE emitido por Afable.

    codigo 1 anula (copia las líneas del original), 2 corrige un texto (montos en cero, la razón
    dice qué cambia) y 3 corrige montos (`lineas`: [{nombre, cantidad, precio}] con lo que se
    descuenta o se suma)."""
    from .nucleo.xmlutil import leer
    if tipo not in (documento.NOTA_CREDITO, documento.NOTA_DEBITO):
        raise ErrorDTE('Solo se emiten notas de crédito (61) o de débito (56).')
    if codigo not in (documento.ANULA, documento.CORRIGE_TEXTO, documento.CORRIGE_MONTOS):
        raise ErrorDTE('Indique si la nota anula, corrige un texto o corrige montos.')
    if original.organization_id != org.id:
        raise ErrorDTE('Ese documento no es de esta empresa.')
    if original.estado == DocumentoEmitido.RECHAZADO:
        raise ErrorDTE('El SII rechazó ese documento: no existe para él y no necesita nota.')
    if original.tipo not in (documento.FACTURA, documento.FACTURA_EXENTA, documento.NOTA_DEBITO,
                             documento.NOTA_CREDITO):
        raise ErrorDTE('Las notas se emiten sobre facturas y otras notas, no sobre guías de despacho.')
    razon = (razon or '').strip()
    if not razon:
        raise ErrorDTE('Escriba la razón de la nota: queda impresa y la ve el cliente.')
    base = documento.desde_xml(leer(original.xml.encode('iso-8859-1')))
    exenta = original.tipo == documento.FACTURA_EXENTA
    if codigo == documento.ANULA:
        nuevas = base.lineas
    elif codigo == documento.CORRIGE_TEXTO:
        nuevas = [documento.Linea(nombre=razon[:80], monto=0)]
    else:
        nuevas = []
        for i, l in enumerate(lineas or [], 1):
            try:
                nuevas.append(documento.Linea(nombre=str(l.get('nombre') or '').strip(), cantidad=l.get('cantidad') or 1,
                                              precio=l['precio'], exento=bool(l.get('exento')) or exenta))
            except (KeyError, ArithmeticError, ValueError, TypeError):
                raise ErrorDTE(f'La línea {i} de la nota no tiene un precio válido.')
        if not nuevas:
            raise ErrorDTE('Indique qué montos corrige la nota (al menos una línea con nombre y precio).')
    if exenta:  # la nota de una factura exenta también es exenta
        for l in nuevas:
            l.exento = True
    nota = documento.Documento(
        tipo=tipo, folio=None, fecha=timezone.localdate(), emisor=emisor(org), receptor=base.receptor, lineas=nuevas,
        referencias=[documento.Referencia(str(original.tipo), str(original.folio), original.fecha, codigo=codigo,
                                          razon=razon)])
    return emitir(org, nota, usuario=usuario, ambiente=original.ambiente)
