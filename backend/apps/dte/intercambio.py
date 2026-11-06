"""El intercambio con clientes y proveedores (ESPEC_SII.md §8).

    enviar_a_cliente()  lo emitido, al cliente: el EnvioDTE con su RUT en la carátula y el PDF.
    recibir()           un EnvioDTE de un proveedor: se revisa, queda en DocumentoRecibido y en el
                        Libro de Compras, y se le devuelve el acuse de recibo.
    aceptar/reclamar()  la respuesta comercial (y el recibo de mercaderías), registrada en el SII.
    revisar_casilla()   la casilla de intercambio de la empresa por IMAP, cada 15 minutos.

Todo emisor electrónico está obligado a recibir DTE: la casilla es la que la empresa declara en el
SII. Un correo con un XML adjunto es el medio mínimo.
"""
import base64
import email
import email.utils
import imaplib
import logging
import time
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from lxml import etree

from . import sii
from .models import ConfiguracionDTE, DocumentoEmitido, DocumentoRecibido
from .nucleo import ErrorDTE, envio, firma, respuesta, ted
from .nucleo import rut as ruts
from .nucleo.documento import TIPOS
from .nucleo.esquemas import validar
from .nucleo.xmlutil import DS, SII, leer

logger = logging.getLogger(__name__)

CADA_CUANTO_CASILLA = timedelta(minutes=15)
CORREOS_POR_REVISION = 50
# Los tipos que admiten recibo de mercaderías (Ley 19.983) y los que registra el SII (Ley 20.956).
TIPOS_CON_RECIBO = {33, 34, 43, 46, 52}
TIPOS_REGISTRO_SII = {33, 34, 43}


def _q(tag):
    return f'{{{SII}}}{tag}'


def _de(nodo, ruta):
    """Texto de una ruta relativa dentro del namespace del SII ('Encabezado/IdDoc/Folio')."""
    return nodo.findtext('/'.join(_q(p) for p in ruta.split('/'))) or ''


def _remitente(org=None):
    """Desde dónde salen los correos del intercambio: la casilla de Afable de la empresa si la usa
    (requiere que DTE_CORREO_DOMINIO esté verificado para envío en el proveedor de correo; si no, el
    proveedor lo rechaza), o el remitente general de Afable."""
    if org is not None:
        cfg = ConfiguracionDTE.de(org)
        if cfg.casilla_afable and direccion_afable(org):
            return direccion_afable(org)
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost')


def _contacto_por_rut(org, rut):
    """La ficha del cliente o proveedor con ese RUT, venga escrito como venga."""
    from apps.finanzas.models import Contacto
    rut = ruts.normalizar(rut)
    numero = rut.split('-')[0]
    for c in Contacto.objects.filter(organization=org, rut__contains=numero[-3:]):
        if ruts.valido(c.rut) and ruts.normalizar(c.rut) == rut:
            return c
    return None


def _certificado(org):
    from .servicio import certificado_activo
    modelo = certificado_activo(org)
    if modelo is None:
        raise ErrorDTE('La empresa no tiene un certificado digital activo para firmar las respuestas.')
    return modelo.cargar()


def _contacto_respuesta(cfg):
    return respuesta.Contacto(correo=cfg.correo_intercambio)


# ── Lo emitido, al cliente ────────────────────────────────────────────────────────────────

def enviar_a_cliente(emitido, forzar=False, correo=None):
    """Le manda al cliente el EnvioDTE (con su RUT en la carátula) y el PDF. Solo en producción y si
    la empresa lo tiene encendido; `forzar` lo manda igual (reenvío a mano o pruebas). Devuelve la
    dirección a la que se mandó, o None si no correspondía o el cliente no tiene correo."""
    org = emitido.organization
    cfg = ConfiguracionDTE.de(org)
    if not forzar and (not cfg.enviar_a_clientes or emitido.ambiente != sii.PRODUCCION):
        return None
    if not correo:
        contacto = _contacto_por_rut(org, emitido.receptor_rut)
        correo = contacto.email if contacto else ''
    if not correo:
        logger.info('dte: %s sin correo del cliente %s; no se le mandó', emitido, emitido.receptor_rut)
        return None
    cert = _certificado(org)
    fecha_res, numero_res = cfg.resolucion(emitido.ambiente)
    dte = leer(emitido.xml.encode('iso-8859-1'))
    datos = envio.armar([dte], envio.Caratula(rut_emisor=org.rut, rut_envia=cert.rut, fecha_resolucion=fecha_res,
                                              numero_resolucion=numero_res, rut_receptor=emitido.receptor_rut),
                        cert)
    nombre = TIPOS.get(emitido.tipo, f'Documento {emitido.tipo}')
    from apps.comercial.models import ConfiguracionComercial
    razon = ConfiguracionComercial.de(org).emisor['razon_social']
    mensaje = EmailMessage(
        subject=f'{nombre} N° {emitido.folio} de {razon}',
        body=(f'Adjuntamos {nombre.lower()} N° {emitido.folio} por ${emitido.monto_total:,}'.replace(',', '.') +
              f', emitida por {razon}.\n\nEl archivo XML es el documento tributario electrónico; el PDF es su '
              'representación impresa.\n'),
        from_email=_remitente(org), to=[correo], reply_to=[cfg.correo_intercambio] if cfg.correo_intercambio else None)
    base = f'{ruts.normalizar(org.rut)}_T{emitido.tipo}F{emitido.folio}'
    mensaje.attach(f'EnvioDTE_{base}.xml', datos, 'application/xml')
    try:
        from .pdf import generar
        mensaje.attach(f'DTE_{base}.pdf', generar(emitido), 'application/pdf')
    except Exception:
        logger.exception('dte: sin PDF para %s; se manda solo el XML', emitido)
    mensaje.send(fail_silently=False)
    return correo


# ── Lo que llega de proveedores ───────────────────────────────────────────────────────────

def _verificar_timbre(ted_el):
    """El timbre con la llave pública del CAF que viene dentro del propio DD."""
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        da = ted_el.find(f'{_q("DD")}/{_q("CAF")}/{_q("DA")}')
        m = int.from_bytes(base64.b64decode(_de(da, 'RSAPK/M')), 'big')
        e = int.from_bytes(base64.b64decode(_de(da, 'RSAPK/E')), 'big')
        llave = rsa.RSAPublicNumbers(e, m).public_key()
        frmt = base64.b64decode(''.join((ted_el.findtext(_q('FRMT')) or '').split()))
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        llave.verify(frmt, ted.aplanar(ted_el.find(_q('DD'))), padding.PKCS1v15(), hashes.SHA1())
        return True
    except Exception:
        return False


def _datos_dte(dte):
    """Lo que se guarda de un DTE recibido: tipo, folio, fecha, emisor, receptor y montos."""
    doc = dte.find(_q('Documento'))
    enc = doc.find(_q('Encabezado'))
    entero = lambda ruta: int(_de(enc, ruta) or 0)  # noqa: E731
    return {
        'id': doc.get('ID'), 'documento': doc,
        'tipo': entero('IdDoc/TipoDTE'), 'folio': entero('IdDoc/Folio'),
        'fecha': date.fromisoformat(_de(enc, 'IdDoc/FchEmis')),
        'fecha_vencimiento': _de(enc, 'IdDoc/FchVenc'),
        'emisor_rut': ruts.normalizar(_de(enc, 'Emisor/RUTEmisor')),
        'emisor_razon_social': _de(enc, 'Emisor/RznSoc'),
        'receptor_rut': ruts.normalizar(_de(enc, 'Receptor/RUTRecep')),
        'monto_neto': entero('Totales/MntNeto'), 'monto_exento': entero('Totales/MntExe'),
        'monto_iva': entero('Totales/IVA'), 'monto_total': entero('Totales/MntTotal'),
    }


def _registrar_compra(org, datos):
    """El documento en el Libro de Compras de Finanzas, con su contraparte (y la regla de categoría
    del proveedor, como al importar el RCV). Si ya estaba (por el RCV), se reutiliza."""
    from apps.finanzas import constantes as fc
    from apps.finanzas.importador import aplicar_regla
    from apps.finanzas.models import Contraparte, DocumentoTributario
    contacto = _contacto_por_rut(org, datos['emisor_rut'])
    cp, _ = Contraparte.objects.get_or_create(
        organization=org, libro=fc.LIBRO_COMPRAS, rut=datos['emisor_rut'],
        defaults={'razon_social': datos['emisor_razon_social'][:255], 'contacto': contacto})
    venc = datos['fecha_vencimiento']
    doc, creado = DocumentoTributario.objects.get_or_create(
        organization=org, libro=fc.LIBRO_COMPRAS, tipo_documento=str(datos['tipo']), rut=datos['emisor_rut'],
        folio=str(datos['folio']),
        defaults={'contraparte': cp, 'razon_social': datos['emisor_razon_social'][:255], 'fecha': datos['fecha'],
                  'fecha_vencimiento': date.fromisoformat(venc) if venc else datos['fecha'] + timedelta(days=cp.plazo),
                  'monto_neto': datos['monto_neto'], 'monto_exento': datos['monto_exento'],
                  'monto_iva': datos['monto_iva'], 'monto_total': datos['monto_total']})
    if creado and cp.regla_activa and cp.categoria_id:
        aplicar_regla(doc, cp)
    return doc


def _digest_envio(raiz):
    for sig in raiz.findall(f'{{{DS}}}Signature'):
        ref = sig.find(f'{{{DS}}}SignedInfo/{{{DS}}}Reference')
        if ref is not None and ref.get('URI') == '#' + (raiz.find(_q('SetDTE')).get('ID') or ''):
            return (ref.findtext(f'{{{DS}}}DigestValue') or '').strip()
    return ''


def recibir(org, datos, origen=DocumentoRecibido.MANUAL, correo_de='', nombre_archivo='EnvioDTE.xml',
            responder=True):
    """Recibe un EnvioDTE de un proveedor. Devuelve {'recibidos': [DocumentoRecibido],
    'estado_envio', 'glosa', 'acuse': bytes|None, 'ignorados': [motivos]}. Lanza ErrorDTE si el
    archivo no es un EnvioDTE."""
    try:
        raiz = leer(datos)
    except etree.XMLSyntaxError:
        raise ErrorDTE('El archivo no se pudo leer como XML.')
    if raiz.tag != _q('EnvioDTE'):
        raise ErrorDTE('El archivo no es un envío de documentos tributarios (EnvioDTE).')
    rut_empresa = ruts.normalizar(org.rut) if org.rut and ruts.valido(org.rut) else ''
    errores_esquema = validar(raiz, 'EnvioDTE')
    firmas = {uri: ok for uri, ok, _ in firma.verificar(raiz)}
    setdte = raiz.find(_q('SetDTE'))
    caratula = setdte.find(_q('Caratula')) if setdte is not None else None
    rut_emisor_envio = _de(caratula, 'RutEmisor') if caratula is not None else ''
    rut_receptor_envio = _de(caratula, 'RutReceptor') if caratula is not None else ''

    if errores_esquema:
        estado_envio = respuesta.ENVIO_ESQUEMA
    elif setdte is None or not firmas.get(setdte.get('ID')):
        estado_envio = respuesta.ENVIO_FIRMA
    elif not rut_empresa or not ruts.valido(rut_receptor_envio) or ruts.normalizar(rut_receptor_envio) != rut_empresa:
        estado_envio = respuesta.ENVIO_RUT_RECEPTOR
    else:
        estado_envio = respuesta.ENVIO_OK

    recibidos, detalles, ignorados = [], [], []
    for dte in (setdte.iterfind(_q('DTE')) if setdte is not None else []):
        try:
            d = _datos_dte(dte)
        except Exception:
            ignorados.append('un documento que no se pudo leer')
            continue
        ref = respuesta.Referencia(d['tipo'], d['folio'], d['fecha'], d['emisor_rut'], d['receptor_rut'],
                                   d['monto_total'])
        if d['receptor_rut'] != rut_empresa:
            ignorados.append(f'{d["tipo"]}-{d["folio"]}: es para el RUT {d["receptor_rut"]}')
            detalles.append((ref, respuesta.DTE_RUT_RECEPTOR, None))
            continue
        if DocumentoRecibido.objects.filter(organization=org, emisor_rut=d['emisor_rut'], tipo=d['tipo'],
                                            folio=d['folio']).exists():
            ignorados.append(f'{d["tipo"]}-{d["folio"]} de {d["emisor_rut"]}: ya se había recibido')
            detalles.append((ref, respuesta.DTE_REPETIDO, None))
            continue
        firma_ok = bool(firmas.get(d['id']))
        timbre_ok = _verificar_timbre(d['documento'].find(_q('TED')))
        observaciones = []
        if errores_esquema:
            observaciones.append('El envío no cumple el esquema del SII: ' + '; '.join(errores_esquema[:3]))
        if not firma_ok:
            observaciones.append('La firma del documento no es válida.')
        if not timbre_ok:
            observaciones.append('El timbre electrónico no corresponde a sus datos.')
        with transaction.atomic():
            recibido = DocumentoRecibido.objects.create(
                organization=org, tipo=d['tipo'], folio=d['folio'], fecha=d['fecha'], emisor_rut=d['emisor_rut'],
                emisor_razon_social=d['emisor_razon_social'][:255], monto_neto=d['monto_neto'],
                monto_exento=d['monto_exento'], monto_iva=d['monto_iva'], monto_total=d['monto_total'],
                xml=envio.dte_suelto(dte).decode('iso-8859-1'), origen=origen, correo_de=correo_de[:200],
                esquema_ok=not errores_esquema, firma_ok=firma_ok, timbre_ok=timbre_ok,
                observaciones='\n'.join(observaciones))
            recibido.documento_tributario = _registrar_compra(org, d)
            recibido.save(update_fields=['documento_tributario'])
        recibidos.append(recibido)
        estado = respuesta.DTE_OK if firma_ok and timbre_ok else (
            respuesta.DTE_FIRMA if not firma_ok else respuesta.DTE_OTRO)
        detalles.append((ref, estado, None if estado != respuesta.DTE_OTRO else 'DTE No Recibido - Timbre invalido'))

    acuse = None
    if responder and rut_empresa and ruts.valido(rut_emisor_envio or ''):
        try:
            cfg = ConfiguracionDTE.de(org)
            acuse = respuesta.recepcion(
                rut_empresa, rut_emisor_envio, nombre_archivo, timezone.localtime().replace(tzinfo=None),
                setdte.get('ID') if setdte is not None else 'SetDoc', estado_envio,
                detalles if estado_envio == respuesta.ENVIO_OK else [], _certificado(org),
                digest=_digest_envio(raiz), cod_envio=int(time.time()) % 10**9,
                contacto=_contacto_respuesta(cfg))
        except ErrorDTE as e:
            logger.warning('dte: sin acuse para el envío de %s: %s', rut_emisor_envio, e)
    if acuse and origen == DocumentoRecibido.CORREO and correo_de:
        try:
            _mandar_respuesta(org, correo_de, 'Acuse de recibo', f'RespuestaDTE_{rut_emisor_envio}.xml', acuse)
            DocumentoRecibido.objects.filter(pk__in=[r.pk for r in recibidos]).update(acuse_enviado_en=timezone.now())
        except Exception:
            logger.exception('dte: no se pudo mandar el acuse a %s', correo_de)
    return {'recibidos': recibidos, 'estado_envio': estado_envio,
            'glosa': respuesta.GLOSAS_ENVIO.get(estado_envio, ''), 'acuse': acuse, 'ignorados': ignorados}


def _mandar_respuesta(org, para, asunto, nombre, datos, otro=None):
    from apps.comercial.models import ConfiguracionComercial
    razon = ConfiguracionComercial.de(org).emisor['razon_social']
    m = EmailMessage(subject=f'{asunto} de {razon}', body=f'{asunto} de {razon}, en el XML adjunto.\n',
                     from_email=_remitente(org), to=[para])
    m.attach(nombre, datos, 'application/xml')
    if otro:
        m.attach(*otro)
    m.send(fail_silently=False)


def _destino_respuesta(recibido):
    if recibido.correo_de:
        return recibido.correo_de
    contacto = _contacto_por_rut(recibido.organization, recibido.emisor_rut)
    return contacto.email if contacto else ''


def _registrar_en_sii(recibido, acciones):
    """Registra la aceptación o el reclamo en el SII (solo 33, 34 y 43). Devuelve el texto de lo
    que respondió. Lanza ErrorDTE si el SII no lo registró."""
    if recibido.tipo not in TIPOS_REGISTRO_SII:
        return ''
    from . import motor
    cfg = ConfiguracionDTE.de(recibido.organization)
    cli = motor.cliente(recibido.organization, cfg.ambiente or sii.PRODUCCION)
    textos = []
    for accion in acciones:
        r = cli.aceptar_o_reclamar(recibido.emisor_rut, recibido.tipo, recibido.folio, accion)
        if r.get('codigo') not in (0, 7):  # 7: el evento ya estaba registrado
            raise ErrorDTE(f'El SII no registró la respuesta ({accion}): {r.get("descripcion") or "sin detalle"}.')
        textos.append(f'{accion}: {r.get("descripcion") or "OK"}')
    return '; '.join(textos)[:300]


def _referencia(recibido):
    return respuesta.Referencia(recibido.tipo, recibido.folio, recibido.fecha, recibido.emisor_rut,
                                ruts.normalizar(recibido.organization.rut), recibido.monto_total)


def aceptar(recibido, usuario=None, recibo_mercaderias=True, recinto='Oficina'):
    """Acepta el documento: lo registra en el SII (ACD y, si se recibieron las mercaderías, ERM) y
    le manda al proveedor la respuesta comercial y el recibo (Ley 19.983)."""
    if recibido.estado != DocumentoRecibido.RECIBIDO:
        raise ErrorDTE(f'El documento ya está {recibido.get_estado_display().lower()}.')
    org = recibido.organization
    cert = _certificado(org)
    acciones = [sii.ACEPTA_CONTENIDO] + ([sii.RECIBO_MERCADERIAS] if recibo_mercaderias else [])
    recibido.respuesta_sii = _registrar_en_sii(recibido, acciones)
    cfg = ConfiguracionDTE.de(org)
    rut_empresa = ruts.normalizar(org.rut)
    xml_resultado = respuesta.resultado(rut_empresa, recibido.emisor_rut, [(_referencia(recibido), respuesta.ACEPTADO,
                                                                           'ACEPTADO OK')],
                                        cert, contacto=_contacto_respuesta(cfg))
    xml_recibos = None
    if recibo_mercaderias and recibido.tipo in TIPOS_CON_RECIBO:
        xml_recibos = respuesta.recibos(rut_empresa, recibido.emisor_rut, [_referencia(recibido)], recinto,
                                        cert.rut, cert, contacto=_contacto_respuesta(cfg))
    recibido.estado = DocumentoRecibido.ACEPTADO
    recibido.save(update_fields=['estado', 'respuesta_sii'])
    _avisar_proveedor(recibido, 'Aceptación comercial', xml_resultado, xml_recibos)
    return {'resultado': xml_resultado, 'recibos': xml_recibos}


def reclamar(recibido, motivo, usuario=None, accion=sii.RECLAMA_CONTENIDO):
    """Reclama el documento: lo registra en el SII (RCD, RFP o RFT; dentro de 8 días) y le manda al
    proveedor el rechazo comercial citando la Ley 19.983."""
    if recibido.estado != DocumentoRecibido.RECIBIDO:
        raise ErrorDTE(f'El documento ya está {recibido.get_estado_display().lower()}.')
    if accion not in (sii.RECLAMA_CONTENIDO, sii.RECLAMO_FALTA_PARCIAL, sii.RECLAMO_FALTA_TOTAL):
        raise ErrorDTE('Indique si reclama el contenido, la falta parcial o la falta total de las mercaderías.')
    motivo = (motivo or '').strip()
    if not motivo:
        raise ErrorDTE('Indique el motivo del reclamo.')
    org = recibido.organization
    cert = _certificado(org)
    recibido.respuesta_sii = _registrar_en_sii(recibido, [accion])
    glosa = f'Rechazado conforme a la Ley 19.983: {motivo}'
    xml_resultado = respuesta.resultado(ruts.normalizar(org.rut), recibido.emisor_rut,
                                        [(_referencia(recibido), respuesta.RECHAZADO, glosa)], cert,
                                        contacto=_contacto_respuesta(ConfiguracionDTE.de(org)))
    recibido.estado = DocumentoRecibido.RECLAMADO
    recibido.observaciones = '\n'.join(filter(None, [recibido.observaciones, f'Reclamado: {motivo}']))
    recibido.save(update_fields=['estado', 'respuesta_sii', 'observaciones'])
    _avisar_proveedor(recibido, 'Reclamo', xml_resultado)
    return {'resultado': xml_resultado}


def _avisar_proveedor(recibido, asunto, xml_resultado, xml_recibos=None):
    para = _destino_respuesta(recibido)
    if not para:
        return
    base = f'{recibido.emisor_rut}_T{recibido.tipo}F{recibido.folio}'
    otro = (f'EnvioRecibos_{base}.xml', xml_recibos, 'application/xml') if xml_recibos else None
    try:
        _mandar_respuesta(recibido.organization, para, asunto, f'RespuestaDTE_{base}.xml', xml_resultado, otro)
    except Exception:
        logger.exception('dte: no se pudo mandar la respuesta comercial a %s', para)


# ── La casilla de intercambio (IMAP) ──────────────────────────────────────────────────────

def _conectar(cfg):
    if not (cfg.imap_servidor and cfg.imap_usuario):
        raise ErrorDTE('Falta el servidor y el usuario de la casilla de intercambio.')
    try:
        imap = imaplib.IMAP4_SSL(cfg.imap_servidor, cfg.imap_puerto or 993, timeout=30)
        imap.login(cfg.imap_usuario, cfg.clave_imap)
    except (imaplib.IMAP4.error, OSError) as e:
        raise ErrorDTE(f'No se pudo entrar a la casilla {cfg.imap_usuario}: {e}')
    return imap


def probar_casilla(cfg):
    imap = _conectar(cfg)
    try:
        estado, _ = imap.select('INBOX', readonly=True)
        if estado != 'OK':
            raise ErrorDTE('La casilla no tiene bandeja de entrada (INBOX).')
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return True


def _adjuntos_xml(mensaje):
    for parte in mensaje.walk():
        nombre = parte.get_filename() or ''
        tipo = parte.get_content_type()
        if nombre.lower().endswith('.xml') or tipo in ('text/xml', 'application/xml'):
            datos = parte.get_payload(decode=True)
            if datos:
                yield nombre or 'EnvioDTE.xml', datos


def revisar_casilla(org):
    """Lee los correos no leídos de la casilla, recibe cada EnvioDTE adjunto y los marca leídos.
    Los XML que no son EnvioDTE (acuses y respuestas de los clientes) se dejan pasar. Devuelve
    cuántos documentos se recibieron."""
    cfg = ConfiguracionDTE.de(org)
    total = 0
    try:
        imap = _conectar(cfg)
    except ErrorDTE as e:
        cfg.imap_error, cfg.imap_revisado_en = str(e)[:500], timezone.now()
        cfg.save(update_fields=['imap_error', 'imap_revisado_en'])
        raise
    try:
        imap.select('INBOX')
        estado, datos = imap.search(None, 'UNSEEN')
        ids = (datos[0].split() if estado == 'OK' and datos and datos[0] else [])[:CORREOS_POR_REVISION]
        for num in ids:
            estado, partes = imap.fetch(num, '(RFC822)')
            if estado != 'OK' or not partes or not isinstance(partes[0], tuple):
                continue
            mensaje = email.message_from_bytes(partes[0][1])
            de = email.utils.parseaddr(mensaje.get('From', ''))[1]
            for nombre, xml in _adjuntos_xml(mensaje):
                try:
                    total += len(recibir(org, xml, DocumentoRecibido.CORREO, correo_de=de,
                                         nombre_archivo=nombre)['recibidos'])
                except ErrorDTE:
                    continue  # un acuse o una respuesta de un cliente: no es un envío de documentos
                except Exception:
                    logger.exception('dte: no se pudo recibir %s de %s', nombre, de)
            imap.store(num, '+FLAGS', '\\Seen')
        cfg.imap_error = ''
    except Exception as e:
        cfg.imap_error = str(e)[:500]
        logger.exception('dte: falló la revisión de la casilla de %s', org)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
        cfg.imap_revisado_en = timezone.now()
        cfg.save(update_fields=['imap_error', 'imap_revisado_en'])
    return total


def procesar_casillas(ahora=None):
    """Revisa las casillas que tocan (cada 15 minutos). Devuelve cuántos documentos llegaron."""
    from .servicio import disponible
    ahora = ahora or timezone.now()
    total = 0
    for cfg in (ConfiguracionDTE.objects.select_related('organization')
                .exclude(imap_servidor='').exclude(imap_usuario='')):
        if cfg.imap_revisado_en and ahora - cfg.imap_revisado_en < CADA_CUANTO_CASILLA:
            continue
        if not disponible(cfg.organization):
            continue
        try:
            total += revisar_casilla(cfg.organization)
        except Exception:
            logger.exception('dte: casilla de %s', cfg.organization_id)
    return total


# ── Certificación: el paso de intercambio ─────────────────────────────────────────────────

def respuestas_certificacion(org, xml_envio):
    """El paso de intercambio de la certificación: el SII le manda a la empresa un EnvioDTE de
    prueba y ella responde con los tres archivos (acuse del envío, resultado comercial y recibo de
    mercaderías). No se registra nada en Compras: son documentos de prueba. Devuelve
    {nombre_archivo: bytes} para subirlos en maullin."""
    try:
        raiz = leer(xml_envio)
    except etree.XMLSyntaxError:
        raise ErrorDTE('El archivo no se pudo leer como XML.')
    if raiz.tag != _q('EnvioDTE'):
        raise ErrorDTE('El archivo no es un EnvioDTE: suba el que entregó el SII para el intercambio.')
    rut_empresa = ruts.normalizar(org.rut)
    setdte = raiz.find(_q('SetDTE'))
    rut_emisor = ruts.normalizar(_de(setdte.find(_q('Caratula')), 'RutEmisor'))
    firmas = {uri: ok for uri, ok, _ in firma.verificar(raiz)}
    if validar(raiz, 'EnvioDTE'):
        estado_envio = respuesta.ENVIO_ESQUEMA
    elif not firmas.get(setdte.get('ID')):
        estado_envio = respuesta.ENVIO_FIRMA
    elif ruts.normalizar(_de(setdte.find(_q('Caratula')), 'RutReceptor')) != rut_empresa:
        estado_envio = respuesta.ENVIO_RUT_RECEPTOR
    else:
        estado_envio = respuesta.ENVIO_OK
    detalles, aceptados = [], []
    for dte in setdte.iterfind(_q('DTE')):
        d = _datos_dte(dte)
        ref = respuesta.Referencia(d['tipo'], d['folio'], d['fecha'], d['emisor_rut'], d['receptor_rut'], d['monto_total'])
        if d['receptor_rut'] != rut_empresa:
            detalles.append((ref, respuesta.DTE_RUT_RECEPTOR, None))
            continue
        ok = bool(firmas.get(d['id'])) and _verificar_timbre(d['documento'].find(_q('TED')))
        detalles.append((ref, respuesta.DTE_OK if ok else respuesta.DTE_FIRMA, None))
        aceptados.append(ref)
    cert = _certificado(org)
    contacto = _contacto_respuesta(ConfiguracionDTE.de(org))
    archivos = {'RespuestaEnvio.xml': respuesta.recepcion(
        rut_empresa, rut_emisor, 'EnvioDTE.xml', timezone.localtime().replace(tzinfo=None), setdte.get('ID'),
        estado_envio, detalles if estado_envio == respuesta.ENVIO_OK else [], cert, digest=_digest_envio(raiz),
        contacto=contacto)}
    if aceptados:
        archivos['ResultadoDTE.xml'] = respuesta.resultado(
            rut_empresa, rut_emisor, [(r, respuesta.ACEPTADO, 'ACEPTADO OK') for r in aceptados], cert,
            id_respuesta=2, contacto=contacto)
        con_recibo = [r for r in aceptados if r.tipo in TIPOS_CON_RECIBO]
        if con_recibo:
            archivos['EnvioRecibos.xml'] = respuesta.recibos(rut_empresa, rut_emisor, con_recibo, 'Oficina central',
                                                             cert.rut, cert, contacto=contacto)
    return archivos


# ── La casilla de Afable (correo entrante por webhook) ────────────────────────────────────
#
# En vez de conectar su propia casilla por IMAP, la empresa usa una dirección de Afable
# (dte-<rut>-<dv>@DTE_CORREO_DOMINIO) y la registra en el SII como correo de intercambio. El
# proveedor de correo entrante (SendGrid Inbound Parse, Mailgun, Postmark, Cloudflare Email
# Workers...) reenvía cada correo, en MIME crudo, a /api/v1/dte/correo-entrante/<secreto>/.

def dominio_casilla():
    return (getattr(settings, 'DTE_CORREO_DOMINIO', '') or '').strip().lower()


def direccion_afable(org):
    """La casilla de intercambio de Afable para la empresa, o '' si no hay dominio o RUT válido."""
    dominio = dominio_casilla()
    if not dominio or not org.rut or not ruts.valido(org.rut):
        return ''
    numero, dv = ruts.partes(org.rut)
    return f'dte-{numero}-{dv.lower()}@{dominio}'


def _empresa_de_direccion(direccion):
    """La empresa dueña de una dirección dte-<rut>-<dv>@dominio, si usa la casilla de Afable."""
    local, _, dominio = (direccion or '').strip().lower().partition('@')
    if dominio != dominio_casilla() or not local.startswith('dte-'):
        return None
    partes = local[4:].split('-')
    if len(partes) != 2 or not ruts.valido(f'{partes[0]}-{partes[1]}'):
        return None
    rut = ruts.normalizar(f'{partes[0]}-{partes[1]}')
    for cfg in ConfiguracionDTE.objects.filter(casilla_afable=True).select_related('organization'):
        org = cfg.organization
        if org.rut and ruts.valido(org.rut) and ruts.normalizar(org.rut) == rut:
            return org
    return None


def recibir_correo(crudo, destinatarios=()):
    """Un correo entrante a la casilla de Afable (MIME crudo). Recibe cada EnvioDTE adjunto en la
    empresa a la que va dirigido (por sus encabezados o por `destinatarios`, el sobre que informa el
    proveedor). Devuelve un resumen; nunca lanza por el contenido del correo."""
    mensaje = email.message_from_bytes(crudo)
    de = email.utils.parseaddr(mensaje.get('From', ''))[1]
    direcciones = list(destinatarios)
    for encabezado in ('To', 'Cc', 'Delivered-To', 'X-Original-To', 'Envelope-To'):
        direcciones += [d for _, d in email.utils.getaddresses(mensaje.get_all(encabezado, []))]
    empresas = {}
    for d in direcciones:
        org = _empresa_de_direccion(d)
        if org is not None:
            empresas[org.id] = org
    resumen = {'de': de, 'empresas': [], 'recibidos': 0, 'ignorados': []}
    if not empresas:
        resumen['ignorados'].append('ningún destinatario es la casilla de Afable de una empresa')
        return resumen
    adjuntos = list(_adjuntos_xml(mensaje))
    if not adjuntos:
        resumen['ignorados'].append('el correo no trae XML')
    for org in empresas.values():
        resumen['empresas'].append(org.slug)
        for nombre, xml in adjuntos:
            try:
                r = recibir(org, xml, DocumentoRecibido.CORREO, correo_de=de, nombre_archivo=nombre)
                resumen['recibidos'] += len(r['recibidos'])
                resumen['ignorados'] += r['ignorados']
            except ErrorDTE as e:
                resumen['ignorados'].append(f'{nombre}: {e}')  # un acuse o respuesta de un cliente
            except Exception:
                logger.exception('dte: no se pudo recibir %s de %s', nombre, de)
                resumen['ignorados'].append(f'{nombre}: error al leerlo')
    return resumen
