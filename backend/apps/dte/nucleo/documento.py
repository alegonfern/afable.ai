"""Los datos de un DTE, sus totales y su XML (ESPEC_SII.md §4).

Tipos: 33 factura, 34 factura exenta, 52 guía de despacho, 56 nota de débito, 61 nota de crédito.
Montos en pesos, enteros. Redondeo [NV, ninguna fuente oficial lo fija]: aritmético (0,5 hacia
arriba) por línea, y el IVA una sola vez sobre el neto total.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree

from . import ErrorDTE
from . import rut as ruts
from . import ted
from .xmlutil import NSMAP, SII, numero, opcional, sub, texto

FACTURA, FACTURA_EXENTA, GUIA, NOTA_DEBITO, NOTA_CREDITO = 33, 34, 52, 56, 61
TIPOS = {FACTURA: 'Factura electrónica', FACTURA_EXENTA: 'Factura no afecta o exenta electrónica',
         GUIA: 'Guía de despacho electrónica', NOTA_DEBITO: 'Nota de débito electrónica',
         NOTA_CREDITO: 'Nota de crédito electrónica'}
TASA_IVA = Decimal('19')
# CodRef de las referencias de notas: 1 anula, 2 corrige texto, 3 corrige montos.
ANULA, CORRIGE_TEXTO, CORRIGE_MONTOS = 1, 2, 3


def redondear(valor):
    return int(Decimal(valor).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass
class Emisor:
    rut: str
    razon_social: str
    giro: str
    actecos: list
    direccion: str
    comuna: str
    ciudad: str = ''
    telefono: str = ''
    correo: str = ''
    sucursal: str = ''
    codigo_sucursal: str = ''  # CdgSIISucur, si se emite desde una sucursal registrada en el SII


@dataclass
class Receptor:
    rut: str
    razon_social: str
    giro: str = ''
    direccion: str = ''
    comuna: str = ''
    ciudad: str = ''
    contacto: str = ''
    correo: str = ''
    codigo_interno: str = ''


@dataclass
class Linea:
    nombre: str
    cantidad: Decimal = None
    precio: Decimal = None
    descripcion: str = ''
    unidad: str = ''
    codigo: str = ''
    exento: bool = False
    descuento_pct: Decimal = None
    descuento_monto: int = None
    recargo_pct: Decimal = None
    recargo_monto: int = None
    # IndExe distinto de 1 (2 no facturable, 4 no venta, 5 a rebajar...); manda sobre `exento`.
    indicador_exencion: int = None
    # Fija el MontoItem (por ejemplo 0 en una nota que corrige texto) en vez de calcularlo.
    monto: int = None

    def __post_init__(self):
        # El SII admite 6 decimales en cantidad y precio (Dec12_6); con eso se calcula todo.
        for campo in ('cantidad', 'precio'):
            v = getattr(self, campo)
            if v is not None:
                setattr(self, campo, Decimal(str(v)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))

    def montos(self):
        """(descuento, recargo, monto de la línea) en pesos."""
        if self.monto is not None:
            return int(self.descuento_monto or 0), int(self.recargo_monto or 0), int(self.monto)
        bruto = Decimal(self.cantidad or 1) * Decimal(self.precio or 0)
        dscto = self.descuento_monto
        if dscto is None and self.descuento_pct:
            dscto = redondear(bruto * Decimal(self.descuento_pct) / 100)
        rcgo = self.recargo_monto
        if rcgo is None and self.recargo_pct:
            rcgo = redondear(bruto * Decimal(self.recargo_pct) / 100)
        dscto, rcgo = int(dscto or 0), int(rcgo or 0)
        return dscto, rcgo, redondear(bruto) - dscto + rcgo


@dataclass
class DescuentoGlobal:
    valor: Decimal
    porcentaje: bool = True
    recargo: bool = False
    glosa: str = ''
    exento: bool = False  # afecta a los ítems exentos en vez de los afectos


@dataclass
class Referencia:
    tipo_documento: str  # '33', '801' (orden de compra), 'SET' en certificación...
    folio: str
    fecha: date
    codigo: int = None
    razon: str = ''
    rut_otro: str = ''
    global_: bool = False


@dataclass
class Transporte:
    patente: str = ''
    rut_transportista: str = ''
    rut_chofer: str = ''
    nombre_chofer: str = ''
    direccion_destino: str = ''
    comuna_destino: str = ''
    ciudad_destino: str = ''


@dataclass
class Documento:
    tipo: int
    folio: int
    fecha: date
    emisor: Emisor
    receptor: Receptor
    lineas: list
    referencias: list = field(default_factory=list)
    descuentos: list = field(default_factory=list)
    forma_pago: int = None  # 1 contado, 2 crédito, 3 sin costo
    fecha_vencimiento: date = None
    indicador_traslado: int = None  # guías: 1 venta, 5 traslado interno, 6 otros no venta, 7 devolución...
    tipo_despacho: int = None
    transporte: Transporte = None
    indicador_servicio: int = None
    tasa_iva: Decimal = TASA_IVA

    @property
    def id(self):
        return f'F{self.folio}T{self.tipo}'


@dataclass
class Totales:
    neto: int = 0
    exento: int = 0
    iva: int = 0
    total: int = 0
    tasa_iva: Decimal = TASA_IVA


def _es_exenta(doc, linea):
    return doc.tipo == FACTURA_EXENTA or linea.exento or linea.indicador_exencion == 1


def totales(doc):
    afecto = exento = 0
    for linea in doc.lineas:
        if linea.indicador_exencion in (2, 3, 4, 5, 6):
            continue  # no facturables, no venta o a rebajar: no suman al total
        monto = linea.montos()[2]
        if _es_exenta(doc, linea):
            exento += monto
        else:
            afecto += monto
    for dr in doc.descuentos:
        base = exento if dr.exento or doc.tipo == FACTURA_EXENTA else afecto
        valor = redondear(Decimal(base) * Decimal(dr.valor) / 100) if dr.porcentaje else int(dr.valor)
        valor = valor if dr.recargo else -valor
        if dr.exento or doc.tipo == FACTURA_EXENTA:
            exento += valor
        else:
            afecto += valor
    iva = redondear(Decimal(afecto) * Decimal(doc.tasa_iva) / 100) if afecto else 0
    return Totales(neto=afecto, exento=exento, iva=iva, total=afecto + exento + iva, tasa_iva=Decimal(doc.tasa_iva))


def validar(doc):
    """Las reglas del SII que el XSD no alcanza a revisar. Lanza ErrorDTE con lo primero que falle."""
    if doc.tipo not in TIPOS:
        raise ErrorDTE(f'Afable no emite documentos tipo {doc.tipo}.')
    if not doc.lineas:
        raise ErrorDTE('El documento no tiene líneas.')
    if len(doc.lineas) > 60:
        raise ErrorDTE(f'El SII admite hasta 60 líneas por documento y este tiene {len(doc.lineas)}.')
    doc.emisor.rut = ruts.normalizar(doc.emisor.rut)
    doc.receptor.rut = ruts.normalizar(doc.receptor.rut)
    e, r = doc.emisor, doc.receptor
    faltan = [n for v, n in ((e.razon_social, 'la razón social'), (e.giro, 'el giro'), (e.actecos, 'la actividad económica'))
              if not v]
    if doc.tipo in (FACTURA, FACTURA_EXENTA, GUIA):
        faltan += [n for v, n in ((e.direccion, 'la dirección'), (e.comuna, 'la comuna')) if not v]
    if faltan:
        raise ErrorDTE(f'Al emisor le falta {", ".join(faltan)}.')
    if doc.tipo in (FACTURA, FACTURA_EXENTA, GUIA):
        faltan = [n for v, n in ((r.giro, 'el giro'), (r.direccion, 'la dirección'), (r.comuna, 'la comuna')) if not v]
        if faltan:
            raise ErrorDTE(f'A {r.razon_social or "el receptor"} le falta {", ".join(faltan)} para emitirle el documento.')
    for i, linea in enumerate(doc.lineas, 1):
        if not texto(linea.nombre):
            raise ErrorDTE(f'La línea {i} no tiene nombre.')
        if linea.precio is not None and Decimal(linea.precio) <= 0 and linea.monto is None:
            raise ErrorDTE(f'La línea {i} tiene precio {linea.precio}: el SII no acepta precios en cero o negativos.')
        if linea.cantidad is not None and Decimal(linea.cantidad) <= 0:
            raise ErrorDTE(f'La línea {i} tiene cantidad {linea.cantidad}: debe ser mayor que cero.')
    if doc.tipo in (NOTA_CREDITO, NOTA_DEBITO):
        if not doc.referencias:
            raise ErrorDTE('Una nota de crédito o débito debe indicar el documento que modifica.')
        if not any(ref.codigo for ref in doc.referencias):
            raise ErrorDTE('Indique si la nota anula, corrige texto o corrige montos del documento que modifica.')
    if doc.tipo == GUIA and not doc.indicador_traslado:
        raise ErrorDTE('La guía de despacho debe indicar el tipo de traslado (venta, traslado interno, devolución...).')
    t = totales(doc)
    if doc.tipo == FACTURA and t.neto <= 0 and t.exento > 0:
        raise ErrorDTE('Todos los ítems son exentos: corresponde una factura exenta (34), no una factura (33).')
    if t.total < 0 or t.neto < 0 or t.exento < 0:
        raise ErrorDTE('Los descuentos dejan el documento con total negativo.')
    return t


def construir(doc, caf, momento=None):
    """El <DTE> completo y timbrado, listo para firmar dentro de su EnvioDTE (envio.py)."""
    t = validar(doc)
    momento = (momento or datetime.now()).replace(microsecond=0)
    dte = etree.Element(f'{{{SII}}}DTE', nsmap=NSMAP, version='1.0')
    documento = sub(dte, 'Documento', ID=doc.id)
    enc = sub(documento, 'Encabezado')

    iddoc = sub(enc, 'IdDoc')
    sub(iddoc, 'TipoDTE', doc.tipo)
    sub(iddoc, 'Folio', doc.folio)
    sub(iddoc, 'FchEmis', doc.fecha.isoformat())
    if doc.tipo == GUIA:
        opcional(iddoc, 'TipoDespacho', doc.tipo_despacho)
        sub(iddoc, 'IndTraslado', doc.indicador_traslado)
    opcional(iddoc, 'IndServicio', doc.indicador_servicio)
    opcional(iddoc, 'FmaPago', doc.forma_pago)
    if doc.fecha_vencimiento and doc.tipo != GUIA:
        sub(iddoc, 'FchVenc', doc.fecha_vencimiento.isoformat())

    e = doc.emisor
    em = sub(enc, 'Emisor')
    sub(em, 'RUTEmisor', e.rut)
    sub(em, 'RznSoc', texto(e.razon_social, 100))
    sub(em, 'GiroEmis', texto(e.giro, 80))
    opcional(em, 'Telefono', texto(e.telefono, 20))
    opcional(em, 'CorreoEmisor', texto(e.correo, 80))
    for acteco in list(e.actecos)[:4]:
        sub(em, 'Acteco', acteco)
    opcional(em, 'Sucursal', texto(e.sucursal, 20))
    opcional(em, 'CdgSIISucur', e.codigo_sucursal)
    opcional(em, 'DirOrigen', texto(e.direccion, 70))
    opcional(em, 'CmnaOrigen', texto(e.comuna, 20))
    opcional(em, 'CiudadOrigen', texto(e.ciudad, 20))

    r = doc.receptor
    rc = sub(enc, 'Receptor')
    sub(rc, 'RUTRecep', r.rut)
    opcional(rc, 'CdgIntRecep', texto(r.codigo_interno, 20))
    sub(rc, 'RznSocRecep', texto(r.razon_social, 100))
    opcional(rc, 'GiroRecep', texto(r.giro, 40))
    opcional(rc, 'Contacto', texto(r.contacto, 80))
    opcional(rc, 'CorreoRecep', texto(r.correo, 80))
    opcional(rc, 'DirRecep', texto(r.direccion, 70))
    opcional(rc, 'CmnaRecep', texto(r.comuna, 20))
    opcional(rc, 'CiudadRecep', texto(r.ciudad, 20))

    tr = doc.transporte
    if tr and any(vars(tr).values()):
        tp = sub(enc, 'Transporte')
        opcional(tp, 'Patente', texto(tr.patente, 8))
        if tr.rut_transportista:
            sub(tp, 'RUTTrans', ruts.normalizar(tr.rut_transportista))
        if tr.rut_chofer and tr.nombre_chofer:
            ch = sub(tp, 'Chofer')
            sub(ch, 'RUTChofer', ruts.normalizar(tr.rut_chofer))
            sub(ch, 'NombreChofer', texto(tr.nombre_chofer, 30))
        opcional(tp, 'DirDest', texto(tr.direccion_destino, 70))
        opcional(tp, 'CmnaDest', texto(tr.comuna_destino, 20))
        opcional(tp, 'CiudadDest', texto(tr.ciudad_destino, 20))

    tot = sub(enc, 'Totales')
    if doc.tipo != FACTURA_EXENTA and t.neto:
        sub(tot, 'MntNeto', t.neto)
    if t.exento or doc.tipo == FACTURA_EXENTA:
        sub(tot, 'MntExe', t.exento)
    if doc.tipo != FACTURA_EXENTA and t.neto:
        sub(tot, 'TasaIVA', numero(t.tasa_iva))
        sub(tot, 'IVA', t.iva)
    sub(tot, 'MntTotal', t.total)

    for i, linea in enumerate(doc.lineas, 1):
        det = sub(documento, 'Detalle')
        sub(det, 'NroLinDet', i)
        if linea.codigo:
            cdg = sub(det, 'CdgItem')
            sub(cdg, 'TpoCodigo', 'INT1')
            sub(cdg, 'VlrCodigo', texto(linea.codigo, 35))
        ind = linea.indicador_exencion or (1 if linea.exento and doc.tipo != FACTURA_EXENTA else None)
        opcional(det, 'IndExe', ind)
        sub(det, 'NmbItem', texto(linea.nombre, 80))
        opcional(det, 'DscItem', texto(linea.descripcion, 1000))
        if linea.cantidad is not None:
            sub(det, 'QtyItem', numero(linea.cantidad))
        opcional(det, 'UnmdItem', texto(linea.unidad, 4))
        if linea.precio is not None:
            sub(det, 'PrcItem', numero(linea.precio))
        dscto, rcgo, monto = linea.montos()
        if dscto:
            opcional(det, 'DescuentoPct', numero(linea.descuento_pct) if linea.descuento_pct else None)
            sub(det, 'DescuentoMonto', dscto)
        if rcgo:
            opcional(det, 'RecargoPct', numero(linea.recargo_pct) if linea.recargo_pct else None)
            sub(det, 'RecargoMonto', rcgo)
        sub(det, 'MontoItem', monto)

    for i, dr in enumerate(doc.descuentos, 1):
        d = sub(documento, 'DscRcgGlobal')
        sub(d, 'NroLinDR', i)
        sub(d, 'TpoMov', 'R' if dr.recargo else 'D')
        opcional(d, 'GlosaDR', texto(dr.glosa, 45))
        sub(d, 'TpoValor', '%' if dr.porcentaje else '$')
        sub(d, 'ValorDR', numero(dr.valor))
        if dr.exento and doc.tipo != FACTURA_EXENTA:
            sub(d, 'IndExeDR', 1)

    for i, ref in enumerate(doc.referencias, 1):
        rf = sub(documento, 'Referencia')
        sub(rf, 'NroLinRef', i)
        sub(rf, 'TpoDocRef', ref.tipo_documento)
        if ref.global_:
            sub(rf, 'IndGlobal', 1)
        sub(rf, 'FolioRef', texto(ref.folio, 18) or '0')
        if ref.rut_otro:
            sub(rf, 'RUTOtr', ruts.normalizar(ref.rut_otro))
        sub(rf, 'FchRef', ref.fecha.isoformat())
        opcional(rf, 'CodRef', ref.codigo)
        opcional(rf, 'RazonRef', texto(ref.razon, 90))

    ted.timbrar(documento, doc, t.total, caf, momento)
    sub(documento, 'TmstFirma', momento.strftime('%Y-%m-%dT%H:%M:%S'))
    return dte


def desde_xml(dte):
    """Un <DTE> (firmado o no) de vuelta a Documento: para emitir la nota que lo corrige o anula,
    o para leer lo que manda un proveedor. Toma solo lo que Afable usa."""
    ns = {'s': SII}

    def t(nodo, ruta, defecto=''):
        return nodo.findtext(ruta, defecto, namespaces=ns) if nodo is not None else defecto

    doc = dte.find('s:Documento', ns)
    enc = doc.find('s:Encabezado', ns)
    em, rc = enc.find('s:Emisor', ns), enc.find('s:Receptor', ns)
    emisor = Emisor(rut=t(em, 's:RUTEmisor'), razon_social=t(em, 's:RznSoc'), giro=t(em, 's:GiroEmis'),
                    actecos=[a.text for a in em.findall('s:Acteco', ns)], direccion=t(em, 's:DirOrigen'),
                    comuna=t(em, 's:CmnaOrigen'), ciudad=t(em, 's:CiudadOrigen'), telefono=t(em, 's:Telefono'),
                    correo=t(em, 's:CorreoEmisor'), sucursal=t(em, 's:Sucursal'), codigo_sucursal=t(em, 's:CdgSIISucur'))
    receptor = Receptor(rut=t(rc, 's:RUTRecep'), razon_social=t(rc, 's:RznSocRecep'), giro=t(rc, 's:GiroRecep'),
                        direccion=t(rc, 's:DirRecep'), comuna=t(rc, 's:CmnaRecep'), ciudad=t(rc, 's:CiudadRecep'),
                        contacto=t(rc, 's:Contacto'), correo=t(rc, 's:CorreoRecep'))
    lineas = []
    for det in doc.findall('s:Detalle', ns):
        dec = lambda ruta: Decimal(t(det, ruta)) if t(det, ruta) else None
        ind = t(det, 's:IndExe')
        lineas.append(Linea(nombre=t(det, 's:NmbItem'), descripcion=t(det, 's:DscItem'), cantidad=dec('s:QtyItem'),
                            precio=dec('s:PrcItem'), unidad=t(det, 's:UnmdItem'), codigo=t(det, 's:CdgItem/s:VlrCodigo'),
                            exento=ind == '1', indicador_exencion=int(ind) if ind and ind != '1' else None,
                            descuento_pct=dec('s:DescuentoPct'),
                            descuento_monto=int(t(det, 's:DescuentoMonto')) if t(det, 's:DescuentoMonto') else None,
                            recargo_monto=int(t(det, 's:RecargoMonto')) if t(det, 's:RecargoMonto') else None,
                            monto=None if t(det, 's:PrcItem') else int(t(det, 's:MontoItem') or 0)))
    iddoc = enc.find('s:IdDoc', ns)
    venc = t(iddoc, 's:FchVenc')
    fp = t(iddoc, 's:FmaPago')
    return Documento(tipo=int(t(iddoc, 's:TipoDTE')), folio=int(t(iddoc, 's:Folio')),
                     fecha=date.fromisoformat(t(iddoc, 's:FchEmis')), emisor=emisor, receptor=receptor, lineas=lineas,
                     forma_pago=int(fp) if fp else None, fecha_vencimiento=date.fromisoformat(venc) if venc else None)
