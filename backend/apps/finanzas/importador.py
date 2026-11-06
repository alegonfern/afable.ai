"""Carga de lo que la empresa descarga del SII: el Registro de Compras y Ventas (compras y
ventas) y el informe de boletas de honorarios recibidas.

⚠️ Las columnas están armadas con el formato conocido del SII y probadas con archivos de
ejemplo (`pruebas/finanzas/`), no con descargas reales todavía. Si un archivo real trae otros
nombres, se agregan en ALIAS: el resto del módulo no cambia.

La carga va en dos pasos, para que nada quede a medio clasificar:
1. `previsualizar`: lee el archivo y deja una Carga en BORRADOR con cada fila y lo que Afable
   propone (categoría, proyecto, si ya está pagada). No crea documentos.
2. `confirmar`: con lo que la persona decidió, crea los documentos y las fichas de los
   proveedores y clientes nuevos.

Reglas:
- Se reconoce el libro por las columnas, o lo indica quien sube.
- Un documento ya cargado (mismo libro, tipo, RUT y folio) no se repite: queda en `ya_estaban`.
  Así se puede volver a subir el mes entero sin miedo.
- Una fila que no se puede leer no frena las demás: queda en `errores` con su fila y folio.
- La categoría propuesta sale, en orden, de la regla de la contraparte o de cómo se clasificó
  su último documento. Lo que quede sin proponer lo puede sugerir la IA.
- Se da por pagado lo que ya venció según el plazo habitual de la contraparte.
"""

import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta

from django.db import transaction

from . import constantes as c
from .models import Asignacion, Carga, Contraparte, DocumentoTributario


def _clave(texto):
    """'Monto IVA Recuperable' → 'monto iva recuperable' (sin tildes, espacios simples)."""
    t = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', t.lower())).strip()


# Campo interno → nombres con los que puede venir la columna (ya pasados por _clave).
ALIAS = {
    'tipo_documento': ['tipo doc', 'tipo documento', 'tipo dte'],
    'folio': ['folio', 'n', 'nro boleta', 'numero', 'n boleta', 'no boleta'],
    'rut': ['rut proveedor', 'rut cliente', 'rut emisor', 'rut contraparte', 'rut'],
    'razon_social': ['razon social', 'nombre o razon social', 'nombre emisor', 'nombre'],
    'fecha': ['fecha docto', 'fecha documento', 'fecha emision', 'fecha'],
    'monto_exento': ['monto exento'],
    'monto_neto': ['monto neto'],
    'monto_iva': ['monto iva recuperable', 'monto iva', 'iva'],
    'monto_iva_no_recuperable': ['monto iva no recuperable'],
    'monto_total': ['monto total', 'total'],
    'brutos': ['brutos', 'monto bruto', 'honorario bruto'],
    'retenido': ['retenido', 'monto retenido', 'retencion'],
    'pagado': ['pagado', 'liquido', 'monto liquido'],
    'estado': ['estado'],
}


def _mapear_columnas(encabezados):
    claves = [_clave(h) for h in encabezados]
    mapa = {}
    for campo, alias in ALIAS.items():
        for nombre in alias:
            if nombre in claves:
                mapa[campo] = claves.index(nombre)
                break
    return mapa


def detectar_libro(encabezados):
    claves = {_clave(h) for h in encabezados}
    if 'rut proveedor' in claves:
        return c.LIBRO_COMPRAS
    if 'rut cliente' in claves:
        return c.LIBRO_VENTAS
    if {'brutos', 'retenido'} <= claves or 'rut emisor' in claves:
        return c.LIBRO_HONORARIOS
    return None


def _monto(valor):
    """'1.284.300' → 1284300; '' → 0; '-12500' → -12500. Montos del SII en pesos, sin decimales."""
    v = (valor or '').strip().replace('$', '').replace(' ', '')
    if not v:
        return 0
    v = v.replace('.', '').replace(',', '.')
    return int(round(float(v)))


def _fecha(valor):
    v = (valor or '').strip()
    for formato in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y'):
        try:
            return datetime.strptime(v, formato).date()
        except ValueError:
            continue
    raise ValueError(f'fecha "{v}" no reconocida')


def _rut(valor):
    """'76.123.456-7' → '76123456-7' (como lo guarda el SII, sin puntos)."""
    v = (valor or '').strip().upper().replace('.', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,8}-[\dK]', v):
        raise ValueError(f'RUT "{valor}" no válido')
    return v


def _leer_texto(contenido: bytes) -> str:
    for codificacion in ('utf-8-sig', 'latin-1'):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode('utf-8', errors='replace')


class ArchivoNoReconocido(ValueError):
    """El archivo no parece del SII: ni el libro ni las columnas mínimas se reconocen."""


def leer_filas(contenido: bytes):
    """Devuelve (encabezados, filas) de un CSV del SII (separado por ; o ,)."""
    texto = _leer_texto(contenido)
    separador = ';' if texto.count(';') >= texto.count(',') else ','
    filas = [f for f in csv.reader(io.StringIO(texto), delimiter=separador) if any(x.strip() for x in f)]
    if not filas:
        raise ArchivoNoReconocido('El archivo está vacío.')
    return filas[0], filas[1:]


def _convertir(fila, mapa, libro):
    def campo(nombre):
        i = mapa.get(nombre)
        return fila[i] if i is not None and i < len(fila) else ''

    if libro == c.LIBRO_HONORARIOS:
        if _clave(campo('estado')) in {'anulada', 'nula', 'anulado'}:
            return None                         # una boleta anulada no es un gasto
        bruto = _monto(campo('brutos'))
        retenido = _monto(campo('retenido'))
        return {
            'tipo_documento': 'BHE',
            'folio': campo('folio').strip(),
            'rut': _rut(campo('rut')),
            'razon_social': campo('razon_social').strip(),
            'fecha': _fecha(campo('fecha')),
            'monto_exento': bruto, 'monto_neto': 0, 'monto_iva': 0,
            'monto_total': bruto, 'monto_retenido': retenido,
        }

    neto = _monto(campo('monto_neto'))
    # El IVA no recuperable es costo de la compra: se suma al total, no al IVA del F29.
    iva = _monto(campo('monto_iva'))
    total = _monto(campo('monto_total'))
    tipo = campo('tipo_documento').strip()
    if not tipo:
        raise ValueError('falta el tipo de documento')
    return {
        'tipo_documento': tipo,
        'folio': campo('folio').strip(),
        'rut': _rut(campo('rut')),
        'razon_social': campo('razon_social').strip(),
        'fecha': _fecha(campo('fecha')),
        'monto_exento': _monto(campo('monto_exento')),
        'monto_neto': neto, 'monto_iva': iva,
        'monto_total': total or (neto + iva + _monto(campo('monto_exento'))),
        'monto_retenido': 0,
    }


def aplicar_regla(documento, contraparte):
    """Clasifica un documento con la regla de su proveedor o cliente y lo deja confirmado."""
    documento.categoria = contraparte.categoria
    if contraparte.medio_pago:
        documento.medio_pago = contraparte.medio_pago
    documento.estado = DocumentoTributario.CONFIRMADO
    documento.origen_clasificacion = DocumentoTributario.ORIGEN_REGLA
    documento.save()
    if contraparte.reparto:
        documento.asignaciones.all().delete()
        Asignacion.objects.bulk_create([
            Asignacion(documento=documento, proyecto_id=r['proyecto'], porcentaje=r['porcentaje'])
            for r in contraparte.reparto
        ])


def _leer(contenido, libro):
    """Lee el archivo sin tocar la base. Devuelve (libro, filas del archivo, válidas, errores)."""
    encabezados, filas = leer_filas(contenido)
    libro = libro or detectar_libro(encabezados)
    if libro not in dict(c.LIBROS):
        raise ArchivoNoReconocido(
            'No se reconoce el archivo. Suba el CSV del Registro de Compras y Ventas o el '
            'informe de boletas de honorarios, tal como lo descarga del SII.')
    mapa = _mapear_columnas(encabezados)
    minimas = {'rut', 'folio', 'fecha'} | ({'brutos'} if libro == c.LIBRO_HONORARIOS else {'monto_total'})
    faltan = minimas - mapa.keys()
    if faltan:
        raise ArchivoNoReconocido(
            f'Al archivo le faltan columnas: {", ".join(sorted(faltan))}. '
            'Revise que sea la descarga del SII sin modificar.')
    validas, errores = [], []
    for numero, fila in enumerate(filas, start=2):          # fila 1 = encabezados
        folio = fila[mapa['folio']].strip() if mapa['folio'] < len(fila) else ''
        try:
            datos = _convertir(fila, mapa, libro)
        except (ValueError, IndexError) as e:
            errores.append({'fila': numero, 'folio': folio, 'motivo': str(e)})
            continue
        if datos is None:
            continue
        if not datos['folio']:
            errores.append({'fila': numero, 'folio': '', 'motivo': 'falta el folio'})
            continue
        validas.append({**datos, 'fila': numero})
    return libro, len(filas), validas, errores


@transaction.atomic
def previsualizar(organization, contenido: bytes, nombre_archivo: str, libro: str = None, usuario=None):
    """Lee el archivo y deja la Carga en borrador con lo que Afable propone para cada fila."""
    libro, total_filas, validas, errores = _leer(contenido, libro)

    existentes = set(DocumentoTributario.objects.filter(organization=organization, libro=libro)
                     .values_list('tipo_documento', 'rut', 'folio'))
    contrapartes = {x.rut: x for x in Contraparte.objects.filter(organization=organization, libro=libro)}
    # Cómo se clasificó por última vez cada RUT: la sugerencia cuando no hay regla.
    historial = {}
    for d in (DocumentoTributario.objects.filter(organization=organization, libro=libro,
                                                 categoria__isnull=False)
              .order_by('rut', '-fecha').values('rut', 'categoria_id')):
        historial.setdefault(d['rut'], d['categoria_id'])

    hoy = date.today()
    previas, ya_estaban, vistos = [], [], set()
    for d in validas:
        clave = (d['tipo_documento'], d['rut'], d['folio'])
        if clave in existentes or clave in vistos:
            ya_estaban.append({'folio': d['folio'], 'razon_social': d['razon_social'],
                               'monto_total': d['monto_total']})
            continue
        vistos.add(clave)
        cp = contrapartes.get(d['rut'])
        plazo = cp.plazo if cp else c.PLAZO_PAGO_POR_DEFECTO
        vence = d['fecha'] + timedelta(days=plazo)
        if cp and cp.regla_activa and cp.categoria_id:
            categoria, origen = cp.categoria_id, DocumentoTributario.ORIGEN_REGLA
        elif d['rut'] in historial:
            categoria, origen = historial[d['rut']], 'historial'
        else:
            categoria, origen = None, ''
        proyecto = None
        if cp and cp.regla_activa and len(cp.reparto) == 1:
            proyecto = cp.reparto[0]['proyecto']
        previas.append({
            **{k: v for k, v in d.items() if k != 'fecha'},
            'n': len(previas), 'fecha': d['fecha'].isoformat(),
            'fecha_vencimiento': vence.isoformat(),
            'categoria': categoria, 'origen': origen, 'proyecto': proyecto,
            'pagado': vence < hoy,
            'contraparte_nueva': cp is None,
            'plazo_dias': plazo,
        })

    return Carga.objects.create(
        organization=organization, libro=libro, nombre_archivo=nombre_archivo[:255],
        subido_por=usuario, filas=total_filas, nuevos=len(previas), duplicados=len(ya_estaban),
        errores=errores, estado=Carga.BORRADOR, filas_previas=previas, ya_estaban=ya_estaban,
    )


@transaction.atomic
def confirmar(carga, decisiones=None):
    """Crea los documentos de una Carga en borrador. `decisiones` cambia lo propuesto por
    fila: {n: {"categoria": id|None, "proyecto": id|None, "pagado": bool}}."""
    if carga.estado != Carga.BORRADOR:
        raise ValueError('Esta carga ya se importó.')
    org, libro = carga.organization, carga.libro
    decisiones = decisiones or {}
    contrapartes = {x.rut: x for x in Contraparte.objects.filter(organization=org, libro=libro)}
    nuevos = 0
    creados = []
    for fila in carga.filas_previas:
        cambio = decisiones.get(fila['n']) or decisiones.get(str(fila['n'])) or {}
        categoria = cambio.get('categoria', fila['categoria'])
        proyecto = cambio.get('proyecto', fila['proyecto'])
        pagado = cambio.get('pagado', fila['pagado'])

        cp = contrapartes.get(fila['rut'])
        if cp is None:
            cp = Contraparte.objects.create(organization=org, libro=libro, rut=fila['rut'],
                                            razon_social=fila['razon_social'])
            contrapartes[fila['rut']] = cp

        conserva_origen = categoria == fila['categoria'] and fila['origen'] in ('regla', 'ia')
        documento, creado = DocumentoTributario.objects.get_or_create(
            organization=org, libro=libro, tipo_documento=fila['tipo_documento'],
            rut=fila['rut'], folio=fila['folio'],
            defaults={
                'carga': carga, 'contraparte': cp, 'razon_social': fila['razon_social'],
                'fecha': date.fromisoformat(fila['fecha']),
                'fecha_vencimiento': date.fromisoformat(fila['fecha_vencimiento']),
                'monto_exento': fila['monto_exento'], 'monto_neto': fila['monto_neto'],
                'monto_iva': fila['monto_iva'], 'monto_total': fila['monto_total'],
                'monto_retenido': fila['monto_retenido'],
                'categoria_id': categoria or None,
                # Se revisó antes de importar: con categoría entra confirmado.
                'estado': (DocumentoTributario.CONFIRMADO if categoria
                           else DocumentoTributario.POR_REVISAR),
                'origen_clasificacion': fila['origen'] if conserva_origen else '',
                'pagado': bool(pagado),
            },
        )
        if not creado:
            continue
        nuevos += 1
        creados.append(documento)
        if proyecto:
            Asignacion.objects.create(documento=documento, proyecto_id=proyecto, porcentaje=100)
        elif cp.regla_activa and len(cp.reparto) > 1:
            Asignacion.objects.bulk_create([
                Asignacion(documento=documento, proyecto_id=r['proyecto'], porcentaje=r['porcentaje'])
                for r in cp.reparto])
    carga.estado = Carga.IMPORTADA
    carga.nuevos = nuevos
    carga.filas_previas = []
    carga.save(update_fields=['estado', 'nuevos', 'filas_previas'])
    if creados:
        from .senales import carga_importada
        carga_importada.send(sender=Carga, carga=carga, documentos=creados)
    return carga


def importar(organization, contenido: bytes, nombre_archivo: str, libro: str = None, usuario=None):
    """Los dos pasos seguidos, aceptando lo propuesto. Para cargas sin revisión y los tests."""
    return confirmar(previsualizar(organization, contenido, nombre_archivo, libro, usuario))
