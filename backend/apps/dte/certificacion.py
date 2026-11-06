"""El asistente de certificación ante el SII (ESPEC_SII.md §9 y §10): lo que Afable hace por la
empresa que debe certificarse para emitir con su RUT.

    interpretar_set(texto)        el set de pruebas que entrega el SII, caso por caso
    generar_set(org)              los DTE del set (básico, guías, exentas), un EnvioDTE por set
    generar_libros(org)           libro de ventas, de compras y de guías del set
    generar_simulacion(org, n)    de 10 a 100 documentos como los de la operación real
    subir_pendientes / consultar  la conversación con maullin (certificación)
    estado_proceso / avanzar      los pasos, con lo que hace Afable y lo que hace la persona en sii.cl

Los envíos de la certificación se suben y se consultan desde acá (no los toma el motor: nacen con
siguiente_intento vacío), porque los libros tienen sus propios estados en el SII.

⚠️ El formato del set está armado con lo que dicen los manuales y la práctica conocida: el SII
no publica una especificación del archivo. Lo que no se entiende queda como problema del caso
(no frena los demás), para revisarlo con el set real que descargue la empresa.
"""
import io
import random
import re
import unicodedata
import zipfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from . import motor, servicio, sii
from .models import Caf, ConfiguracionDTE, DocumentoEmitido, EnvioSII, ProcesoCertificacion
from .nucleo import ErrorDTE, documento as d, envio, libro
from .nucleo import rut as ruts
from .nucleo.xmlutil import SII, leer

CERT = sii.CERTIFICACION

# ── Interpretar el set ────────────────────────────────────────────────────────────────────

BASICO, GUIAS, EXENTA, LIBRO_COMPRAS, LIBRO_VENTAS, LIBRO_GUIAS, OTRO = (
    'basico', 'guias', 'exenta', 'libro_compras', 'libro_ventas', 'libro_guias', 'otro')
NOMBRES_SET = {BASICO: 'Set básico', GUIAS: 'Set guía de despacho', EXENTA: 'Set factura exenta',
               LIBRO_COMPRAS: 'Set libro de compras', LIBRO_VENTAS: 'Set libro de ventas',
               LIBRO_GUIAS: 'Set libro de guías', OTRO: 'Set no reconocido'}
SETS_DE_DOCUMENTOS = (BASICO, GUIAS, EXENTA)

# Nombre del documento en el set -> código SII. Se comparan sin acentos ni mayúsculas.
TIPOS_SET = [
    ('FACTURA NO AFECTA O EXENTA ELECTRONICA', 34), ('FACTURA EXENTA ELECTRONICA', 34),
    ('NOTA DE CREDITO ELECTRONICA', 61), ('NOTA DE DEBITO ELECTRONICA', 56),
    ('GUIA DE DESPACHO ELECTRONICA', 52), ('GUIA DE DESPACHO', 52), ('FACTURA ELECTRONICA', 33),
]
# Los del libro de compras incluyen documentos en papel.
TIPOS_COMPRA = [
    ('FACTURA DE COMPRA ELECTRONICA', 46), ('FACTURA DE COMPRA', 45),
    ('FACTURA NO AFECTA O EXENTA ELECTRONICA', 34), ('FACTURA EXENTA ELECTRONICA', 34), ('FACTURA EXENTA', 32),
    ('NOTA DE CREDITO ELECTRONICA', 61), ('NOTA DE CREDITO', 60),
    ('NOTA DE DEBITO ELECTRONICA', 56), ('NOTA DE DEBITO', 55),
    ('FACTURA ELECTRONICA', 33), ('FACTURA', 30),
]
# Motivo de la guía -> IndTraslado.
MOTIVOS = [('VENTA POR EFECTUAR', 2), ('CONSIGNACION', 3), ('ENTREGA GRATUITA', 4), ('TRASLADO', 5),
           ('ENTRE BODEGAS', 5), ('DEVOLUCION', 7), ('EXPORTACION', 8), ('VENTA', 1), ('OTRO', 6)]


def _plano(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().upper()


def _tipo_de(texto, tabla=TIPOS_SET):
    t = _plano(texto)
    for nombre, codigo in tabla:
        if t.startswith(nombre):
            return codigo
    return None


def _num(texto):
    """'1.489' o '1489' o '14,5' -> Decimal. None si no es un número."""
    t = str(texto).strip().replace('%', '').replace('$', '').strip()
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')
    t = t.replace(',', '.')
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def _celdas(linea):
    """Las celdas de una línea del set: separadas por tabs o por dos o más espacios."""
    return [c.strip() for c in re.split(r'\t+| {2,}', linea.strip()) if c.strip()]


def _codigo_referencia(razon):
    r = _plano(razon)
    if 'ANULA' in r:
        return d.ANULA
    if 'CORRIGE' in r and 'MONTO' not in r:
        return d.CORRIGE_TEXTO
    return d.CORRIGE_MONTOS  # devolución, modifica monto, descuento...


def _tipo_despacho(texto):
    """TipoDespacho: 1 por cuenta del receptor; 2 del emisor a instalaciones del cliente; 3 del
    emisor a otras instalaciones (traslado interno)."""
    t = _plano(texto)
    if not t:
        return None
    if 'CLIENTE' in t and 'EMISOR' not in t:
        return 1
    if 'CLIENTE' in t:
        return 2
    return 3


def _bloques(texto, patron):
    """Corta `texto` en bloques que empiezan en cada línea que calza con `patron`."""
    partes, actual = [], None
    for linea in texto.splitlines():
        if re.match(patron, _plano(linea)):
            actual = [linea]
            partes.append(actual)
        elif actual is not None:
            actual.append(linea)
    return partes


def _items(lineas, encabezado_idx):
    """Los ítems de una tabla: la fila de encabezado dice qué columnas hay después de ITEM."""
    columnas = [_plano(c) for c in _celdas(lineas[encabezado_idx])][1:]
    items, problemas = [], []
    for linea in lineas[encabezado_idx + 1:]:
        if not linea.strip() or set(linea.strip()) <= {'=', '-'}:
            continue
        celdas = _celdas(linea)
        if _plano(celdas[0]).startswith('DESCUENTO GLOBAL'):
            break
        nombre, valores = celdas[0], celdas[1:]
        item = {'nombre': nombre, 'cantidad': None, 'precio': None, 'descuento_pct': None, 'unidad': '',
                'exento': 'EXENTO' in _plano(nombre)}
        for col, valor in zip(columnas, valores):
            if col.startswith('CANTIDAD'):
                item['cantidad'] = str(_num(valor)) if _num(valor) is not None else None
            elif col.startswith('PRECIO'):
                item['precio'] = str(_num(valor)) if _num(valor) is not None else None
            elif col.startswith('DESCUENTO'):
                item['descuento_pct'] = str(_num(valor)) if _num(valor) is not None else None
            elif col.startswith('UNIDAD'):
                item['unidad'] = valor
            elif col.startswith('VALOR EXENTO') or col.startswith('EXENTO'):
                item['exento'] = True
                item['precio'] = str(_num(valor)) if _num(valor) is not None else item['precio']
        if len(valores) > len(columnas):
            problemas.append(f'La fila «{linea.strip()}» trae más valores que columnas.')
        if item['cantidad'] is None and valores:
            problemas.append(f'No se entendió la cantidad de «{nombre}».')
        items.append(item)
    return items, problemas


def _caso(bloque, tipo_set):
    cabecera = re.search(r'CASO\s+([\d-]+)', _plano(bloque[0]))
    caso = {'caso': cabecera.group(1) if cabecera else '', 'tipo': None, 'documento': '', 'items': [],
            'descuento_global_pct': None, 'referencia_caso': None, 'referencia_documento': '', 'razon': '',
            'codigo_referencia': None, 'motivo': '', 'traslado_por': '', 'indicador_traslado': None,
            'tipo_despacho': None, 'problemas': []}
    lineas = bloque[1:]
    for i, linea in enumerate(lineas):
        p = _plano(linea)
        celdas = _celdas(linea)
        if not p or set(p) <= {'=', '-'}:
            continue
        if p.startswith('DOCUMENTO'):
            caso['documento'] = re.sub(r'^DOCUMENTO:?\s*', '', p)
            caso['tipo'] = _tipo_de(caso['documento'])
        elif p.startswith('RAZON REFERENCIA'):
            caso['razon'] = re.sub(r'^RAZON REFERENCIA:?\s*', '', p)
            caso['codigo_referencia'] = _codigo_referencia(caso['razon'])
        elif p.startswith('REFERENCIA'):
            texto = re.sub(r'^REFERENCIA:?\s*', '', p)
            m = re.search(r'CASO\s+([\d-]+)', texto)
            caso['referencia_caso'] = m.group(1) if m else None
            caso['referencia_documento'] = texto.split(' CORRESPONDIENTE')[0]
        elif p.startswith('MOTIVO'):
            caso['motivo'] = re.sub(r'^MOTIVO:?\s*', '', p)
            caso['indicador_traslado'] = next((c for n, c in MOTIVOS if n in caso['motivo']), 6)
        elif p.startswith('TRASLADO POR'):
            caso['traslado_por'] = re.sub(r'^TRASLADO POR:?\s*', '', p)
            caso['tipo_despacho'] = _tipo_despacho(caso['traslado_por'])
        elif p.startswith('DESCUENTO GLOBAL'):
            pct = next((_num(c) for c in reversed(celdas) if _num(c) is not None), None)
            caso['descuento_global_pct'] = str(pct) if pct is not None else None
            if pct is None:
                caso['problemas'].append('No se entendió el porcentaje del descuento global.')
        elif celdas and _plano(celdas[0]) == 'ITEM':
            caso['items'], problemas = _items(lineas, i)
            caso['problemas'] += problemas
            for resto in lineas[i + 1:]:  # el descuento global puede venir después de la tabla
                if _plano(resto).startswith('DESCUENTO GLOBAL'):
                    pct = next((_num(c) for c in reversed(_celdas(resto)) if _num(c) is not None), None)
                    caso['descuento_global_pct'] = str(pct) if pct is not None else None
            break
    if tipo_set == EXENTA and caso['tipo'] in (33, None) and 'EXENTA' in caso['documento']:
        caso['tipo'] = 34
    if caso['tipo'] is None:
        caso['problemas'].append(f'No se reconoce el tipo de documento «{caso["documento"] or "?"}».')
    if caso['tipo'] in (56, 61) and not caso['referencia_caso']:
        caso['problemas'].append('La nota no indica a qué caso corresponde.')
    if caso['tipo'] in (33, 34, 52) and not caso['items']:
        caso['problemas'].append('El caso no trae ítems.')
    return caso


def _compras(bloque):
    """Las filas del set de libro de compras: una línea con el documento y su folio, y otra con
    la observación y los montos (exento, afecto) alineados bajo sus columnas."""
    filas, problemas, factor = [], [], None
    col_exento = col_afecto = None
    pendiente = None
    for linea in bloque[1:]:
        expandida = linea.expandtabs(8)
        p = _plano(linea)
        if not p or set(p) <= {'=', '-'}:
            continue
        if 'MONTO EXENTO' in p and 'MONTO AFECTO' in p:
            col_exento, col_afecto = expandida.upper().find('MONTO EXENTO'), expandida.upper().find('MONTO AFECTO')
            continue
        if p.startswith('TIPO DOCUMENTO'):
            continue
        if p.startswith('FACTOR DE PROPORCIONALIDAD'):
            m = re.search(r'(\d+[.,]\d+)', p)
            factor = m.group(1).replace(',', '.') if m else None
            continue
        grupos = [(m.start(), m.group(0)) for m in re.finditer(r'\S+(?: \S+)*', expandida)]
        if pendiente is None:
            tipo = _tipo_de(grupos[0][1], TIPOS_COMPRA) if grupos else None
            folio = _num(grupos[-1][1]) if len(grupos) > 1 else None
            if tipo is None or folio is None:
                problemas.append(f'No se entendió la fila «{linea.strip()}».')
                continue
            pendiente = {'tipo': tipo, 'documento': _plano(grupos[0][1]), 'folio': int(folio)}
            continue
        montos = [(pos, _num(g)) for pos, g in grupos[1:] if _num(g) is not None]
        exento = afecto = 0
        for pos, valor in montos:
            if col_exento is not None and col_afecto is not None:
                es_exento = abs(pos - col_exento) < abs(pos - col_afecto)
            else:
                es_exento = len(montos) == 2 and (pos, valor) == montos[0]
            if es_exento:
                exento = int(valor)
            else:
                afecto = int(valor)
        observacion = _plano(grupos[0][1]) if grupos else ''
        ref = re.search(r'(FACTURA(?: ELECTRONICA)?)\s+(\d+)\s*$', observacion)
        pendiente.update({'observacion': observacion, 'exento': exento, 'afecto': afecto,
                          'referencia_tipo': _tipo_de(ref.group(1), TIPOS_COMPRA) if ref else None,
                          'referencia_folio': int(ref.group(2)) if ref else None})
        filas.append(pendiente)
        pendiente = None
    if pendiente is not None:
        problemas.append(f'La fila del folio {pendiente["folio"]} no trae sus montos.')
    return filas, factor, problemas


def interpretar_set(texto):
    """El set de pruebas como una lista de sets: [{tipo_set, titulo, atencion, casos, compras,
    factor, problemas}]. Tolerante a tabs, espacios, acentos y mayúsculas."""
    if isinstance(texto, bytes):
        try:
            texto = texto.decode('utf-8')
        except UnicodeDecodeError:
            texto = texto.decode('iso-8859-1')
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    sets = []
    for bloque in _bloques(texto, r'^SET\b'):
        titulo = _plano(bloque[0])
        m = re.search(r'ATENCION:?\s*(\d+)', titulo)
        if 'LIBRO DE COMPRAS' in titulo:
            tipo_set = LIBRO_COMPRAS
        elif 'LIBRO DE VENTAS' in titulo:
            tipo_set = LIBRO_VENTAS
        elif 'LIBRO DE GUIAS' in titulo:
            tipo_set = LIBRO_GUIAS
        elif 'GUIA' in titulo:
            tipo_set = GUIAS
        elif 'EXENTA' in titulo:
            tipo_set = EXENTA
        elif 'BASICO' in titulo:
            tipo_set = BASICO
        else:
            tipo_set = OTRO
        s = {'tipo_set': tipo_set, 'nombre': NOMBRES_SET[tipo_set], 'titulo': titulo,
             'atencion': m.group(1) if m else '', 'casos': [], 'compras': [], 'factor': None, 'problemas': [],
             'texto': '\n'.join(bloque).strip()}
        if tipo_set in SETS_DE_DOCUMENTOS:
            s['casos'] = [_caso(b, tipo_set) for b in _bloques('\n'.join(bloque[1:]), r'^CASO\s+[\d-]+')]
            if not s['casos']:
                s['problemas'].append('El set no trae casos.')
        elif tipo_set == LIBRO_COMPRAS:
            s['compras'], s['factor'], s['problemas'] = _compras(bloque)
        elif tipo_set == OTRO:
            s['problemas'].append('Afable no reconoce este set: revíselo con el texto original.')
        sets.append(s)
    if not sets:
        raise ErrorDTE('El archivo no parece un set de pruebas del SII: no trae ninguna línea "SET ...".')
    return sets


# ── Datos ficticios para los receptores y proveedores ────────────────────────────────────

_CLIENTES = [
    ('Comercial Los Andes SpA', 'Venta al por menor de artículos de ferretería', 'Av. Apoquindo 3000', 'Las Condes'),
    ('Distribuidora Pacífico Ltda', 'Venta al por mayor de alimentos', 'Av. Brasil 1250', 'Valparaíso'),
    ('Constructora Cordillera SA', 'Construcción de edificios', 'Los Carrera 455', 'Concepción'),
    ('Servicios Integrales Sur SpA', 'Servicios de asesoría empresarial', 'Picarte 820', 'Valdivia'),
    ('Importadora Norte Grande Ltda', 'Importación de maquinaria', 'Av. Grecia 1501', 'Antofagasta'),
    ('Agrícola Valle Central SpA', 'Cultivo de frutas', 'Camino a Rancagua km 5', 'Rancagua'),
    ('Tecnología Austral SpA', 'Desarrollo de software', 'Av. Providencia 1208', 'Providencia'),
    ('Transportes del Maule Ltda', 'Transporte de carga por carretera', '1 Sur 950', 'Talca'),
]
_PROVEEDORES = ['Insumos Industriales SpA', 'Papelería Central Ltda', 'Ferretería El Roble SpA',
                'Servicios Gráficos Ltda', 'Agroinsumos del Sur SpA']


def _rut_ficticio(i, base=76100000):
    n = base + i * 111111
    return f'{n}-{ruts.dv(n)}'


def receptor_ficticio(i):
    nombre, giro, direccion, comuna = _CLIENTES[i % len(_CLIENTES)]
    return d.Receptor(rut=_rut_ficticio(i), razon_social=nombre, giro=giro, direccion=direccion, comuna=comuna,
                      ciudad=comuna)


# ── Requisitos y generación de documentos ────────────────────────────────────────────────

def proceso(org):
    p, _ = ProcesoCertificacion.objects.get_or_create(organization=org)
    return p


def guardar_set(org, texto):
    sets = interpretar_set(texto)
    p = proceso(org)
    if isinstance(texto, bytes):
        try:
            texto = texto.decode('utf-8')
        except UnicodeDecodeError:
            texto = texto.decode('iso-8859-1')
    p.set_texto, p.casos = texto, sets
    p.save()
    return p


def _tipos_necesarios(sets):
    tipos = {}
    for s in sets:
        if s['tipo_set'] in SETS_DE_DOCUMENTOS:
            for c in s['casos']:
                if c['tipo']:
                    tipos[c['tipo']] = tipos.get(c['tipo'], 0) + 1
    return tipos


def requisitos(org, tipos=None):
    """Lo que falta para generar en certificación: certificado, fecha de resolución y folios."""
    cfg = ConfiguracionDTE.de(org)
    empresa = next(p for p in servicio.estado(org, CERT)['pasos'] if p['clave'] == 'empresa')
    falta = list(empresa['falta'])
    if servicio.certificado_activo(org) is None:
        falta.append('subir el certificado digital de quien firma')
    if not cfg.certificacion_fecha:
        falta.append('la fecha de resolución que el SII publica en "datos de su empresa" del ambiente de certificación')
    if not org.rut or not ruts.valido(org.rut):
        falta.append('el RUT de la empresa')
    disponibles = servicio.folios(org, CERT)
    for tipo, n in sorted((tipos or {}).items()):
        if disponibles.get(tipo, 0) < n:
            falta.append(f'folios de certificación de {d.TIPOS.get(tipo, tipo).lower()} '
                         f'(se necesitan {n}, hay {disponibles.get(tipo, 0)})')
    return falta


def _contexto(org):
    cfg = ConfiguracionDTE.de(org)
    cert = servicio.certificado_activo(org).cargar()
    emisor = servicio.emisor(org)
    emisor.rut = ruts.normalizar(org.rut)
    momento = timezone.localtime().replace(tzinfo=None, microsecond=0)
    caratula = envio.Caratula(rut_emisor=emisor.rut, rut_envia=cert.rut, fecha_resolucion=cfg.certificacion_fecha,
                              numero_resolucion=0)
    return cfg, cert, emisor, momento, caratula


def _guardar_envio(org, docs, proposito, descripcion, cert, caratula, momento):
    """Arma y firma el EnvioDTE de `docs` [(Documento, CafNucleo)] y lo guarda con sus DTE.
    Nace sin siguiente_intento: lo sube este asistente, no el motor."""
    dtes = [d.construir(doc, caf, momento) for doc, caf in docs]
    datos = envio.armar(dtes, caratula, cert, momento)
    e = EnvioSII.objects.create(organization=org, ambiente=CERT, proposito=proposito, descripcion=descripcion[:200],
                                xml=datos.decode('iso-8859-1'), siguiente_intento=None)
    for (doc, _), dte in zip(docs, envio.dtes_de(datos)):
        t = d.totales(doc)
        DocumentoEmitido.objects.create(
            organization=org, ambiente=CERT, tipo=doc.tipo, folio=doc.folio, fecha=doc.fecha,
            receptor_rut=doc.receptor.rut, receptor_razon_social=doc.receptor.razon_social[:255],
            monto_neto=t.neto, monto_exento=t.exento, monto_iva=t.iva, monto_total=t.total,
            xml=envio.dte_suelto(dte).decode('iso-8859-1'), envio=e)
    return e


class _Folios:
    """Toma folios de certificación y cachea el CAF cargado de cada uno."""

    def __init__(self, org):
        self.org, self._cafs = org, {}

    def tomar(self, tipo):
        caf, folio = servicio._tomar_folio(self.org, CERT, tipo)
        if caf.id not in self._cafs:
            self._cafs[caf.id] = caf.cargar()
        return folio, self._cafs[caf.id]


def _referencia_set(caso, folio, hoy):
    return d.Referencia('SET', str(folio), hoy, razon=f'CASO {caso}')


def _documento_caso(caso, tipo_set, hechos, emisor, receptor, hoy):
    """El Documento (sin folio) de un caso. `hechos` tiene los casos ya armados, para las notas."""
    tipo = caso['tipo']
    if tipo_set == EXENTA and tipo == 33:
        tipo = 34
    lineas, descuentos = [], []
    for it in caso['items']:
        lineas.append(d.Linea(nombre=it['nombre'], cantidad=Decimal(it['cantidad']) if it['cantidad'] else None,
                              precio=Decimal(it['precio']) if it['precio'] else None, unidad=it.get('unidad', ''),
                              descuento_pct=Decimal(it['descuento_pct']) if it['descuento_pct'] else None,
                              exento=it['exento'] and tipo != 34))
    if caso['descuento_global_pct']:
        descuentos.append(d.DescuentoGlobal(valor=Decimal(caso['descuento_global_pct']), porcentaje=True,
                                            glosa='DESCUENTO GLOBAL ITEMES AFECTOS'))
    doc = d.Documento(tipo=tipo, folio=None, fecha=hoy, emisor=emisor, receptor=receptor, lineas=lineas,
                      descuentos=descuentos)
    if tipo == 52:
        doc.indicador_traslado = caso['indicador_traslado'] or 1
        doc.tipo_despacho = caso['tipo_despacho']
        if doc.indicador_traslado == 5:  # traslado interno: el receptor es la misma empresa
            doc.receptor = d.Receptor(rut=emisor.rut, razon_social=emisor.razon_social, giro=emisor.giro,
                                      direccion=emisor.direccion, comuna=emisor.comuna, ciudad=emisor.ciudad)
        if doc.tipo_despacho in (2, 3):
            doc.transporte = d.Transporte(direccion_destino=doc.receptor.direccion, comuna_destino=doc.receptor.comuna,
                                          ciudad_destino=doc.receptor.ciudad)
    if tipo in (56, 61):
        original = hechos.get(caso['referencia_caso'])
        if original is None:
            raise ErrorDTE(f'El caso {caso["caso"]} referencia al caso {caso["referencia_caso"]}, que no está generado.')
        odoc = original
        doc.receptor = odoc.receptor
        codigo = caso['codigo_referencia'] or d.CORRIGE_MONTOS
        if codigo == d.CORRIGE_TEXTO:
            doc.lineas = [d.Linea(nombre=caso['razon'] or 'CORRIGE TEXTO', monto=0)]
            doc.descuentos = []
        elif codigo == d.ANULA or not doc.lineas:
            doc.lineas = [d.Linea(**{k: getattr(l, k) for k in l.__dataclass_fields__}) for l in odoc.lineas]
            doc.descuentos = list(odoc.descuentos)
        else:
            # Devolución o diferencia de precio: precio, descuento y exención de la línea original.
            por_nombre = {_plano(l.nombre): l for l in odoc.lineas}
            for l in doc.lineas:
                o = por_nombre.get(_plano(l.nombre))
                if o is None:
                    continue
                if l.precio is None:
                    l.precio = o.precio
                if l.descuento_pct is None:
                    l.descuento_pct = o.descuento_pct
                l.exento = o.exento
        if odoc.tipo == 34:  # lo que corrige a una exenta es exento
            for l in doc.lineas:
                l.exento = True
        doc._referencia = (odoc.tipo, odoc.folio, odoc.fecha, codigo, caso['razon'])
    return doc


def generar_set(org, usuario=None):
    """Los DTE de los sets de documentos del set de pruebas cargado, en su orden: un EnvioDTE por
    set. Todo o nada: si un caso falla, no se gasta ningún folio."""
    p = proceso(org)
    if not p.casos:
        raise ErrorDTE('Primero cargue el set de pruebas que descargó del SII.')
    sets = [s for s in p.casos if s['tipo_set'] in SETS_DE_DOCUMENTOS]
    if not sets:
        raise ErrorDTE('El set cargado no trae sets de documentos (básico, guías o exentas).')
    con_problemas = [f'{c["caso"]}: {pr}' for s in sets for c in s['casos'] for pr in c['problemas']]
    if con_problemas:
        raise ErrorDTE('Hay casos que Afable no entendió: ' + '; '.join(con_problemas[:5]))
    falta = requisitos(org, _tipos_necesarios(sets))
    if falta:
        raise ErrorDTE('Para generar el set falta: ' + '; '.join(falta) + '.')
    cfg, cert, emisor, momento, caratula = _contexto(org)
    hoy = momento.date()
    envios = []
    with transaction.atomic():
        folios = _Folios(org)
        hechos, n_receptor = {}, 0
        for s in sets:
            docs = []
            for caso in s['casos']:
                receptor = receptor_ficticio(n_receptor)
                if caso['tipo'] in (33, 34) or (caso['tipo'] == 52 and caso['indicador_traslado'] != 5):
                    n_receptor += 1
                doc = _documento_caso(caso, s['tipo_set'], hechos, emisor, receptor, hoy)
                doc.folio, caf = folios.tomar(doc.tipo)
                doc.referencias = [_referencia_set(caso['caso'], doc.folio, hoy)]
                if hasattr(doc, '_referencia'):
                    otipo, ofolio, ofecha, codigo, razon = doc._referencia
                    doc.referencias.append(d.Referencia(str(otipo), str(ofolio), ofecha, codigo=codigo,
                                                        razon=razon or 'CORRIGE'))
                hechos[caso['caso']] = doc
                docs.append((doc, caf))
            e = _guardar_envio(org, docs, EnvioSII.SET_PRUEBAS, f'{s["nombre"]} (atención {s["atencion"]})',
                               cert, caratula, momento)
            envios.append(e)
        p.notas = {**p.notas, 'ultimo_set': {'envios': [e.id for e in envios], 'fecha': hoy.isoformat()}}
        p.save(update_fields=['notas', 'actualizado_en'])
    return envios


# ── Libros ───────────────────────────────────────────────────────────────────────────────

def _referencia_de(xml):
    """La referencia a otro documento (no la del SET) de un DTE guardado."""
    raiz = leer(xml.encode('iso-8859-1'))
    for ref in raiz.iter(f'{{{SII}}}Referencia'):
        tipo = ref.findtext(f'{{{SII}}}TpoDocRef')
        if tipo and tipo.isdigit():
            return int(tipo), int(ref.findtext(f'{{{SII}}}FolioRef'))
    return None, None


def _ultimo_set(org):
    p = proceso(org)
    ids = (p.notas.get('ultimo_set') or {}).get('envios') or []
    if not ids:
        raise ErrorDTE('Primero genere el set de pruebas: los libros se arman con sus documentos.')
    return list(DocumentoEmitido.objects.filter(organization=org, envio_id__in=ids).order_by('envio_id', 'id'))


def generar_libros(org, guias_anuladas=(), folio_notificacion_guias=3):
    """Libro de ventas (facturas y notas del set), de compras (el set de compras) y de guías.
    `guias_anuladas`: los casos de guía que el set pide informar como anulados."""
    p = proceso(org)
    falta = requisitos(org)
    if falta:
        raise ErrorDTE('Para generar los libros falta: ' + '; '.join(falta) + '.')
    cfg, cert, emisor, momento, _ = _contexto(org)
    docs = _ultimo_set(org)
    periodo = docs[0].fecha.strftime('%Y-%m')
    base = dict(rut_emisor=emisor.rut, rut_envia=cert.rut, periodo=periodo, fecha_resolucion=cfg.certificacion_fecha,
                numero_resolucion=0)
    creados = []

    ventas = []
    for x in docs:
        if x.tipo == 52:
            continue
        rtipo, rfolio = _referencia_de(x.xml) if x.tipo in (56, 61) else (None, None)
        ventas.append(libro.DetalleLibro(tipo=x.tipo, folio=x.folio, fecha=x.fecha, rut=x.receptor_rut,
                                         razon_social=x.receptor_razon_social, exento=x.monto_exento,
                                         neto=x.monto_neto, iva=x.monto_iva, total=x.monto_total,
                                         referencia_tipo=rtipo, referencia_folio=rfolio))
    if ventas:
        datos = libro.libro_compra_venta(libro.VENTA, libro.CaratulaLibro(**base, folio_notificacion=1), ventas, cert,
                                         momento)
        creados.append(EnvioSII.objects.create(organization=org, ambiente=CERT, proposito=EnvioSII.LIBRO_VENTAS,
                                               descripcion=f'Libro de ventas {periodo}', xml=datos.decode('iso-8859-1')))

    set_compras = next((s for s in p.casos if s['tipo_set'] == LIBRO_COMPRAS), None)
    if set_compras and set_compras['compras']:
        compras = []
        fecha = date.fromisoformat(periodo + '-01')
        for i, f in enumerate(set_compras['compras']):
            neto, exento = f['afecto'], f['exento']
            iva = d.redondear(Decimal(neto) * d.TASA_IVA / 100)
            det = libro.DetalleLibro(tipo=f['tipo'], folio=f['folio'], fecha=fecha, rut=_rut_ficticio(i, 77200000),
                                     razon_social=_PROVEEDORES[i % len(_PROVEEDORES)], exento=exento, neto=neto, iva=iva,
                                     referencia_tipo=f.get('referencia_tipo'), referencia_folio=f.get('referencia_folio'))
            obs = f.get('observacion', '')
            if 'USO COMUN' in obs:
                det.iva, det.iva_uso_comun = 0, iva
            elif 'ENTREGA GRATUITA' in obs:
                det.iva, det.iva_no_recuperable = 0, [(4, iva)]
            elif 'SIN DERECHO A CREDITO' in obs:  # [NV] código 1 o 9 según el caso
                det.iva, det.iva_no_recuperable = 0, [(9, iva)]
            elif 'RETENCION TOTAL' in obs:
                det.otros_impuestos, det.iva_retenido_total = [(libro.RETENCION_TOTAL, d.TASA_IVA, iva)], iva
            compras.append(det)
        datos = libro.libro_compra_venta(libro.COMPRA, libro.CaratulaLibro(**base, folio_notificacion=2), compras, cert,
                                         momento, factor_proporcionalidad=set_compras.get('factor'))
        creados.append(EnvioSII.objects.create(organization=org, ambiente=CERT, proposito=EnvioSII.LIBRO_COMPRAS,
                                               descripcion=f'Libro de compras {periodo}', xml=datos.decode('iso-8859-1')))

    guias = [x for x in docs if x.tipo == 52]
    if guias:
        casos_guia = [c for s in p.casos if s['tipo_set'] == GUIAS for c in s['casos']]
        anulados = {c['caso'] for c in casos_guia if c['caso'] in set(guias_anuladas)}
        detalles = []
        for x, caso in zip(guias, casos_guia):
            raiz = leer(x.xml.encode('iso-8859-1'))
            traslado = int(raiz.findtext(f'.//{{{SII}}}IndTraslado') or 1)
            detalles.append(libro.DetalleGuia(folio=x.folio, fecha=x.fecha, rut=x.receptor_rut,
                                              razon_social=x.receptor_razon_social, tipo_traslado=traslado,
                                              neto=x.monto_neto, iva=x.monto_iva, total=x.monto_total,
                                              anulado=2 if caso['caso'] in anulados else None))
        datos = libro.libro_guias(libro.CaratulaLibro(**base, folio_notificacion=folio_notificacion_guias), detalles,
                                  cert, momento)
        creados.append(EnvioSII.objects.create(organization=org, ambiente=CERT, proposito=EnvioSII.LIBRO_GUIAS,
                                               descripcion=f'Libro de guías {periodo}', xml=datos.decode('iso-8859-1')))
    if not creados:
        raise ErrorDTE('No hay documentos para armar libros.')
    p.notas = {**p.notas, 'libros': {'envios': [e.id for e in creados], 'periodo': periodo}}
    p.save(update_fields=['notas', 'actualizado_en'])
    return creados


# ── Simulación ───────────────────────────────────────────────────────────────────────────

_CATALOGO = [('Servicio de mantención mensual', 45000, 180000), ('Asesoría contable', 60000, 250000),
             ('Caja de tornillos 100 un', 3500, 9000), ('Saco de cemento 25 kg', 4500, 7500),
             ('Licencia de software anual', 120000, 480000), ('Despacho a domicilio', 5000, 25000),
             ('Resma papel carta', 3900, 5500), ('Hora de soporte técnico', 25000, 45000),
             ('Pintura látex 1 galón', 12000, 22000), ('Curso de capacitación', 90000, 350000)]


def generar_simulacion(org, cantidad=20, semilla=None):
    """Un EnvioDTE con documentos como los de la operación real (sin referencias SET): facturas
    (algunas con ítems exentos y descuentos), exentas, notas de crédito y débito, y guías, según
    los folios de certificación que tenga la empresa."""
    cantidad = int(cantidad)
    if not 10 <= cantidad <= 100:
        raise ErrorDTE('La simulación lleva entre 10 y 100 documentos.')
    disponibles = servicio.folios(org, CERT)
    falta = requisitos(org, {33: 1})
    if falta:
        raise ErrorDTE('Para generar la simulación falta: ' + '; '.join(falta) + '.')
    azar = random.Random(semilla)
    cfg, cert, emisor, momento, caratula = _contexto(org)
    hoy = momento.date()
    plan = []
    for i in range(cantidad):
        r = azar.random()
        tipo = 33
        if r < 0.12 and disponibles.get(34, 0) > plan.count(34):
            tipo = 34
        elif r < 0.24 and disponibles.get(61, 0) > plan.count(61) and plan.count(33) > plan.count(61):
            tipo = 61
        elif r < 0.30 and disponibles.get(56, 0) > plan.count(56) and plan.count(33) > plan.count(56):
            tipo = 56
        elif r < 0.38 and disponibles.get(52, 0) > plan.count(52):
            tipo = 52
        if disponibles.get(tipo, 0) <= plan.count(tipo):
            tipo = 33
        plan.append(tipo)
    if disponibles.get(33, 0) < plan.count(33):
        raise ErrorDTE(f'Faltan folios de factura de certificación: se necesitan {plan.count(33)}.')

    with transaction.atomic():
        folios = _Folios(org)
        docs, facturas = [], []
        for i, tipo in enumerate(plan):
            receptor = receptor_ficticio(azar.randrange(len(_CLIENTES)))
            if tipo in (61, 56):
                odoc = azar.choice(facturas)
                linea = odoc.lineas[0]
                cant = max(Decimal(1), (linea.cantidad or Decimal(1)) // 2)
                doc = d.Documento(tipo=tipo, folio=None, fecha=hoy, emisor=emisor, receptor=odoc.receptor, lineas=[
                    d.Linea(nombre=linea.nombre, cantidad=cant, precio=linea.precio, exento=linea.exento)])
                razon = 'Devolución de mercaderías' if tipo == 61 else 'Intereses por mora'
                doc.folio, caf = folios.tomar(tipo)
                doc.referencias = [d.Referencia(str(odoc.tipo), str(odoc.folio), odoc.fecha, codigo=d.CORRIGE_MONTOS,
                                                razon=razon)]
            else:
                lineas = []
                for nombre, minimo, maximo in azar.sample(_CATALOGO, azar.randint(1, 4)):
                    lineas.append(d.Linea(nombre=nombre, cantidad=azar.randint(1, 20),
                                          precio=azar.randrange(minimo, maximo, 100),
                                          descuento_pct=azar.choice([None, None, None, 5, 10])))
                if tipo == 33 and azar.random() < 0.2:
                    lineas.append(d.Linea(nombre='Libro técnico', cantidad=1, precio=azar.randrange(8000, 30000, 100),
                                          exento=True))
                doc = d.Documento(tipo=tipo, folio=None, fecha=hoy, emisor=emisor, receptor=receptor, lineas=lineas,
                                  forma_pago=azar.choice([1, 2]))
                if tipo == 52:
                    doc.indicador_traslado, doc.tipo_despacho = 1, 2
                    doc.transporte = d.Transporte(direccion_destino=receptor.direccion, comuna_destino=receptor.comuna)
                doc.folio, caf = folios.tomar(tipo)
                if tipo == 33:
                    facturas.append(doc)
            docs.append((doc, caf))
        e = _guardar_envio(org, docs, EnvioSII.SIMULACION, f'Simulación ({cantidad} documentos)', cert, caratula,
                           momento)
        p = proceso(org)
        p.notas = {**p.notas, 'simulacion': {'envio': e.id, 'fecha': hoy.isoformat()}}
        p.save(update_fields=['notas', 'actualizado_en'])
    return e


# ── Subir y consultar en maullin ─────────────────────────────────────────────────────────

# [NV] Estados de QueryEstUp para libros: LOK aceptado (cuadrado), LTC cuadrado con tolerancia,
# LNC no cuadrado (reparo), LR* rechazado (LRH esquema, LRF firma, LRC carátula...).
LIBRO_ACEPTADO, LIBRO_REPAROS = {'LOK'}, {'LTC', 'LNC'}
LIBROS = (EnvioSII.LIBRO_VENTAS, EnvioSII.LIBRO_COMPRAS, EnvioSII.LIBRO_GUIAS)


def envios(org):
    return EnvioSII.objects.filter(organization=org, ambiente=CERT).exclude(proposito=EnvioSII.EMISION)


def subir_pendientes(org):
    """Sube a maullin los envíos de la certificación que esperan. Devuelve los que subió."""
    pendientes = list(envios(org).filter(estado=EnvioSII.POR_SUBIR))
    if not pendientes:
        return []
    cli = motor.cliente(org, CERT)
    subidos = []
    for e in pendientes:
        e.intentos += 1
        try:
            r = cli.enviar(e.xml.encode('iso-8859-1'), org.rut, nombre=f'{e.proposito}_{e.id}.xml')
        except sii.ErrorSII as error:
            e.error, e.respuesta = str(error), (error.detalle or '')[:20000]
            if error.codigo in motor.STATUS_DEFINITIVOS:
                e.estado = EnvioSII.RECHAZADO
                e.documentos.update(estado=DocumentoEmitido.RECHAZADO, detalle_estado=str(error)[:500])
            e.save()
            continue
        e.estado, e.trackid, e.error, e.respuesta = EnvioSII.SUBIDO, r.trackid, '', r.xml[:20000]
        e.save()
        e.documentos.update(estado=DocumentoEmitido.ENVIADO)
        subidos.append(e)
    return subidos


def _resultado(e, r):
    """El estado final de un envío de la certificación según lo que respondió el SII, o None si
    todavía está en proceso."""
    if e.proposito in LIBROS:
        if r.estado in LIBRO_ACEPTADO:
            return EnvioSII.ACEPTADO
        if r.estado in LIBRO_REPAROS:
            return EnvioSII.REPAROS
        if r.estado.startswith('LR') or r.estado in sii.ENVIO_RECHAZADO:
            return EnvioSII.RECHAZADO
        return None
    if not r.final:
        return None
    if r.estado in sii.ENVIO_RECHAZADO or any(x['rechazados'] for x in r.resumen):
        return EnvioSII.RECHAZADO
    if r.estado in ('RPR', 'RLV') or any(x['reparos'] for x in r.resumen):
        return EnvioSII.REPAROS
    return EnvioSII.ACEPTADO


def consultar(org):
    """Pregunta a maullin por los envíos subidos. En la certificación todo debe quedar aceptado
    sin reparos: con reparos o rechazo, se corrige y se vuelve a generar (con folios nuevos)."""
    subidos = list(envios(org).filter(estado=EnvioSII.SUBIDO))
    if not subidos:
        return []
    cli = motor.cliente(org, CERT)
    p = proceso(org)
    for e in subidos:
        r = cli.estado_envio(org.rut, e.trackid)
        e.estado_sii, e.glosa, e.resumen, e.respuesta = r.estado, r.descripcion[:500], r.resumen, r.xml[:20000]
        e.intentos += 1
        final = _resultado(e, r)
        if final:
            e.estado = final
            estado_doc = {EnvioSII.ACEPTADO: DocumentoEmitido.ACEPTADO, EnvioSII.REPAROS: DocumentoEmitido.REPAROS,
                          EnvioSII.RECHAZADO: DocumentoEmitido.RECHAZADO}[final]
            e.documentos.update(estado=estado_doc, detalle_estado=r.descripcion[:500])
            if final == EnvioSII.ACEPTADO:
                aceptados = p.notas.get('aceptados', {})
                aceptados[str(e.id)] = {'proposito': e.proposito, 'trackid': e.trackid,
                                        'fecha': timezone.localdate().isoformat(), 'descripcion': e.descripcion}
                p.notas = {**p.notas, 'aceptados': aceptados}
        e.save()
    p.save(update_fields=['notas', 'actualizado_en'])
    return subidos


# ── Intercambio y muestras (los arman intercambio.py y pdf.py) ───────────────────────────

def responder_intercambio(org, xml_envio):
    """Las tres respuestas del paso de intercambio para el EnvioDTE que el SII le mandó a la
    empresa: {nombre_archivo: bytes}. Las arma intercambio.py."""
    try:
        from . import intercambio
    except ImportError:
        raise ErrorDTE('El intercambio todavía no está disponible en Afable (falta intercambio.py).')
    funcion = getattr(intercambio, 'respuestas_certificacion', None)
    if funcion is None:
        raise ErrorDTE('El intercambio de Afable todavía no arma las respuestas de la certificación '
                       '(falta intercambio.respuestas_certificacion).')
    respuestas = funcion(org, xml_envio)
    p = proceso(org)
    p.notas = {**p.notas, 'intercambio': {'fecha': timezone.localdate().isoformat(), 'archivos': sorted(respuestas)}}
    p.save(update_fields=['notas', 'actualizado_en'])
    return respuestas


def muestras_impresas(org):
    """Un .zip con el PDF de cada documento del set (y su copia cedible, si corresponde) y uno de
    cada tipo de la simulación, un documento por archivo, como los pide el SII."""
    try:
        from . import pdf
    except ImportError:
        raise ErrorDTE('El PDF de los documentos todavía no está disponible en Afable (falta pdf.py).')
    generar = getattr(pdf, 'generar', None)
    if generar is None:
        raise ErrorDTE('El PDF de Afable todavía no está listo (falta pdf.generar).')
    docs = _ultimo_set(org)
    sim_id = (proceso(org).notas.get('simulacion') or {}).get('envio')
    if sim_id:
        vistos = set()
        for x in DocumentoEmitido.objects.filter(organization=org, envio_id=sim_id).order_by('id'):
            if x.tipo not in vistos:
                vistos.add(x.tipo)
                docs.append(x)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for x in docs:
            z.writestr(f'T{x.tipo}F{x.folio}.pdf', generar(x))
            if x.tipo in (33, 34) or (x.tipo == 52 and _traslado(x) == 1):
                z.writestr(f'T{x.tipo}F{x.folio}_cedible.pdf', generar(x, cedible=True))
    return salida.getvalue()


def _traslado(x):
    return int(leer(x.xml.encode('iso-8859-1')).findtext(f'.//{{{SII}}}IndTraslado') or 0)


# ── Los pasos ────────────────────────────────────────────────────────────────────────────

PASOS = [
    {'clave': 'postulacion', 'titulo': 'Postulación',
     'afable': 'Nada todavía: este paso es suyo en sii.cl.',
     'usted': ['El representante legal postula en sii.cl › Factura electrónica › Sistema de facturación propio o '
               'de mercado › Postulación, con su certificado digital.',
               'Registre el correo de contacto SII y la casilla de intercambio (la que configuró en Afable).',
               'En el ambiente de certificación (maullin.sii.cl), en "Mantención de usuarios autorizados", dé a quien '
               'firma los perfiles Firmar Doctos, Enviar Doctos y Solicitar Folios.',
               'Pida folios (CAF) de certificación para cada tipo de documento y súbalos en Afable.',
               'Anote en Afable la fecha de resolución que aparece en "datos de su empresa" del ambiente de certificación.']},
    {'clave': ProcesoCertificacion.SET_PRUEBAS, 'titulo': 'Set de pruebas',
     'afable': 'Lee el set, arma cada caso (con la referencia SET), lo firma, lo sube a maullin y consulta el '
               'resultado. Después arma y sube los libros que pida el set.',
     'usted': ['Descargue el set en maullin.sii.cl › "Generación nuevo set de pruebas" y súbalo a Afable.',
               'Cuando Afable muestre el set aceptado sin reparos, declare el avance en maullin indicando el número '
               'de envío (trackid) y la fecha que Afable le muestra.',
               'Si el set trae libros, declare también los envíos de los libros.']},
    {'clave': ProcesoCertificacion.SIMULACION, 'titulo': 'Simulación',
     'afable': 'Arma entre 10 y 100 documentos como los de su operación real, los sube y consulta el resultado.',
     'usted': ['Cuando quede aceptada sin reparos, declare el avance de la simulación en maullin con su trackid.']},
    {'clave': ProcesoCertificacion.INTERCAMBIO, 'titulo': 'Intercambio de información',
     'afable': 'Con el envío que le manda el SII, arma el acuse de recibo, el recibo de mercaderías y el '
               'resultado comercial, firmados.',
     'usted': ['Descargue en maullin el envío de intercambio (o tómelo de la casilla de intercambio) y súbalo a Afable.',
               'Suba en maullin las tres respuestas que Afable le entrega y declare el avance.']},
    {'clave': ProcesoCertificacion.MUESTRAS, 'titulo': 'Muestras de impresión',
     'afable': 'Arma el PDF de cada documento del set y uno de cada tipo de la simulación, con sus copias cedibles.',
     'usted': ['Envíe las muestras por la revisión de maullin (o al correo que indique el SII) y espere la aprobación.']},
    {'clave': ProcesoCertificacion.DECLARACION, 'titulo': 'Declaración de cumplimiento',
     'afable': 'Nada: este paso es del representante legal.',
     'usted': ['El representante legal firma en sii.cl la declaración de cumplimiento de requisitos.',
               'Con la autorización, pida folios de producción en palena.sii.cl, súbalos en Afable y active '
               'la facturación en producción.']},
    {'clave': ProcesoCertificacion.TERMINADO, 'titulo': 'Autorizada',
     'afable': 'Emite en producción.', 'usted': []},
]
ORDEN = [x['clave'] for x in PASOS if x['clave'] != 'postulacion']


def _envio(e):
    return {'id': e.id, 'proposito': e.proposito, 'proposito_nombre': e.get_proposito_display(),
            'descripcion': e.descripcion, 'estado': e.estado, 'estado_nombre': e.get_estado_display(),
            'trackid': e.trackid, 'estado_sii': e.estado_sii, 'glosa': e.glosa, 'resumen': e.resumen,
            'error': e.error, 'documentos': e.documentos.count(), 'creado_en': e.creado_en,
            'actualizado_en': e.actualizado_en}


def estado_proceso(org):
    p = proceso(org)
    actual = ORDEN.index(p.paso)
    pasos = []
    for paso in PASOS:
        clave = paso['clave']
        if clave == 'postulacion':
            listo, es_actual = bool(p.casos) or actual > 0, False
        else:
            i = ORDEN.index(clave)
            listo, es_actual = i < actual, i == actual
        pasos.append({**paso, 'listo': listo, 'actual': es_actual})
    sets = [{'tipo_set': s['tipo_set'], 'nombre': s['nombre'], 'atencion': s['atencion'],
             'casos': [{'caso': c['caso'], 'tipo': c['tipo'], 'documento': c['documento'],
                        'items': len(c['items']), 'referencia_caso': c['referencia_caso'], 'razon': c['razon'],
                        'problemas': c['problemas']} for c in s['casos']],
             'compras': len(s['compras']), 'problemas': s['problemas']} for s in p.casos]
    return {
        'paso': p.paso, 'pasos': pasos, 'sets': sets,
        'requisitos': requisitos(org, _tipos_necesarios(p.casos)),
        'folios': servicio.folios(org, CERT),
        'envios': [_envio(e) for e in envios(org)[:50]],
        'aceptados': list((p.notas.get('aceptados') or {}).values()),
        'notas': {k: v for k, v in p.notas.items() if k != 'aceptados'},
    }


def avanzar(org, paso):
    if paso not in ORDEN:
        raise ErrorDTE('Paso de certificación no válido.')
    p = proceso(org)
    p.paso = paso
    p.save(update_fields=['paso', 'actualizado_en'])
    if paso == ProcesoCertificacion.TERMINADO:
        cfg = ConfiguracionDTE.de(org)
        if cfg.camino == ConfiguracionDTE.CERTIFICAR:
            cfg.camino = ConfiguracionDTE.YA_EMISOR
            cfg.save(update_fields=['camino', 'actualizado_en'])
    return p
