"""Los libros electrónicos que pide la certificación (ESPEC_SII.md §10.1): el de Compras y Ventas
(IECV, LibroCV_v10.xsd) y el de Guías de Despacho (LibroGuia_v10.xsd).

En producción el RCV reemplazó al IECV; acá se arman como los pide el set de pruebas: TipoLibro
ESPECIAL, TipoEnvio TOTAL y FolioNotificacion 1 (ventas) o 2 (compras). Se firman igual que el
EnvioDTE (firma.firmar, con firma.c14n) y se validan contra su XSD antes de devolverlos.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from lxml import etree

from . import ErrorDTE, firma
from . import rut as ruts
from .documento import redondear
from .xmlutil import NSMAP, SII, XSI, leer, numero, serializar, sub, texto

VENTA, COMPRA = 'VENTA', 'COMPRA'
# Código de impuesto de la retención total del IVA (factura de compra, tabla 7 del formato DTE).
RETENCION_TOTAL = 15


@dataclass
class DetalleLibro:
    """Una línea del libro: un documento con sus montos. `total` se calcula si no se indica."""
    tipo: int
    folio: int
    fecha: date
    rut: str
    razon_social: str
    exento: int = 0
    neto: int = 0
    iva: int = 0  # IVA recuperable (en compras) o débito (en ventas)
    tasa: Decimal = Decimal('19')
    total: int = None
    referencia_tipo: int = None
    referencia_folio: int = None
    iva_uso_comun: int = 0
    iva_no_recuperable: list = field(default_factory=list)  # [(código, monto)]
    otros_impuestos: list = field(default_factory=list)  # [(código, tasa, monto)]
    iva_retenido_total: int = 0

    def monto_total(self):
        if self.total is not None:
            return int(self.total)
        return (self.exento + self.neto + self.iva + self.iva_uso_comun
                + sum(m for _, m in self.iva_no_recuperable) - self.iva_retenido_total)


@dataclass
class DetalleGuia:
    folio: int
    fecha: date
    rut: str
    razon_social: str
    tipo_traslado: int  # el IndTraslado de la guía: 1 venta, 5 traslado interno...
    neto: int = 0
    iva: int = 0
    tasa: Decimal = Decimal('19')
    total: int = None
    anulado: int = None  # 1 folio anulado (no se usó); 2 guía anulada después de emitida
    referencia_tipo: int = None
    referencia_folio: int = None
    referencia_fecha: date = None

    def monto_total(self):
        return int(self.total) if self.total is not None else self.neto + self.iva


@dataclass
class CaratulaLibro:
    rut_emisor: str
    rut_envia: str
    periodo: str  # 'AAAA-MM'
    fecha_resolucion: date
    numero_resolucion: int
    folio_notificacion: int = None
    tipo_libro: str = 'ESPECIAL'
    tipo_envio: str = 'TOTAL'


def _raiz(nombre, esquema):
    raiz = etree.Element(f'{{{SII}}}{nombre}', nsmap=NSMAP)
    raiz.set(f'{{{XSI}}}schemaLocation', f'http://www.sii.cl/SiiDte {esquema}')
    raiz.set('version', '1.0')
    return raiz


def _caratula(envio, c, operacion=None):
    car = sub(envio, 'Caratula')
    sub(car, 'RutEmisorLibro', ruts.normalizar(c.rut_emisor))
    sub(car, 'RutEnvia', ruts.normalizar(c.rut_envia))
    sub(car, 'PeriodoTributario', c.periodo)
    sub(car, 'FchResol', c.fecha_resolucion.isoformat())
    sub(car, 'NroResol', int(c.numero_resolucion))
    if operacion:
        sub(car, 'TipoOperacion', operacion)
    sub(car, 'TipoLibro', c.tipo_libro)
    sub(car, 'TipoEnvio', c.tipo_envio)
    if c.folio_notificacion is not None:
        sub(car, 'FolioNotificacion', int(c.folio_notificacion))
    return car


def _firmar_y_cerrar(raiz, envio_libro, certificado, momento, esquema):
    sub(envio_libro, 'TmstFirma', momento.strftime('%Y-%m-%dT%H:%M:%S'))
    etree.indent(raiz, space=' ')
    firma.firmar(envio_libro, certificado)
    datos = serializar(raiz)
    from .esquemas import validar
    errores = validar(leer(datos), esquema)
    if errores:
        raise ErrorDTE('El libro no cumple el esquema del SII: ' + '; '.join(errores[:5]))
    malas = [motivo for _, ok, motivo in firma.verificar(leer(datos)) if not ok]
    if malas:
        raise ErrorDTE('Firma inválida en el libro: ' + '; '.join(malas))
    return datos


def libro_compra_venta(operacion, caratula, detalles, certificado, momento=None, factor_proporcionalidad=None):
    """El LibroCompraVenta firmado, en ISO-8859-1. `factor_proporcionalidad` (0 a 1) es el del IVA
    de uso común del período (solo compras)."""
    if operacion not in (VENTA, COMPRA):
        raise ErrorDTE('El libro es de VENTA o de COMPRA.')
    if not detalles:
        raise ErrorDTE('El libro no tiene documentos.')
    momento = (momento or datetime.now()).replace(microsecond=0)
    raiz = _raiz('LibroCompraVenta', 'LibroCV_v10.xsd')
    envio_libro = sub(raiz, 'EnvioLibro', ID='LibroVentas' if operacion == VENTA else 'LibroCompras')
    _caratula(envio_libro, caratula, operacion)

    resumen = sub(envio_libro, 'ResumenPeriodo')
    tipos = []
    for d in detalles:
        if d.tipo not in tipos:
            tipos.append(d.tipo)
    for tipo in tipos:
        ds = [d for d in detalles if d.tipo == tipo]
        tp = sub(resumen, 'TotalesPeriodo')
        sub(tp, 'TpoDoc', tipo)
        sub(tp, 'TotDoc', len(ds))
        sub(tp, 'TotMntExe', sum(d.exento for d in ds))
        sub(tp, 'TotMntNeto', sum(d.neto for d in ds))
        con_iva = [d for d in ds if d.iva]
        if con_iva:
            sub(tp, 'TotOpIVARec', len(con_iva))
        sub(tp, 'TotMntIVA', sum(d.iva for d in ds))
        codigos = []
        for d in ds:
            for cod, _ in d.iva_no_recuperable:
                if cod not in codigos:
                    codigos.append(cod)
        for cod in codigos:
            nr = sub(tp, 'TotIVANoRec')
            sub(nr, 'CodIVANoRec', cod)
            sub(nr, 'TotOpIVANoRec', sum(1 for d in ds if any(c == cod for c, _ in d.iva_no_recuperable)))
            sub(nr, 'TotMntIVANoRec', sum(m for d in ds for c, m in d.iva_no_recuperable if c == cod))
        uso_comun = [d for d in ds if d.iva_uso_comun]
        if uso_comun:
            total_uc = sum(d.iva_uso_comun for d in uso_comun)
            sub(tp, 'TotOpIVAUsoComun', len(uso_comun))
            sub(tp, 'TotIVAUsoComun', total_uc)
            if factor_proporcionalidad is not None:
                fct = Decimal(str(factor_proporcionalidad))
                sub(tp, 'FctProp', numero(fct))
                sub(tp, 'TotCredIVAUsoComun', redondear(total_uc * fct))
        impuestos = []
        for d in ds:
            for cod, _, _ in d.otros_impuestos:
                if cod not in impuestos:
                    impuestos.append(cod)
        for cod in impuestos:
            oi = sub(tp, 'TotOtrosImp')
            sub(oi, 'CodImp', cod)
            sub(oi, 'TotMntImp', sum(m for d in ds for c, _, m in d.otros_impuestos if c == cod))
        retenidos = [d for d in ds if d.iva_retenido_total]
        if retenidos:
            sub(tp, 'TotOpIVARetTotal', len(retenidos))
            sub(tp, 'TotIVARetTotal', sum(d.iva_retenido_total for d in retenidos))
        sub(tp, 'TotMntTotal', sum(d.monto_total() for d in ds))

    for d in detalles:
        det = sub(envio_libro, 'Detalle')
        sub(det, 'TpoDoc', d.tipo)
        sub(det, 'NroDoc', d.folio)
        if d.neto or d.iva or d.iva_uso_comun or d.iva_no_recuperable:
            sub(det, 'TasaImp', numero(d.tasa))
        sub(det, 'FchDoc', d.fecha.isoformat())
        sub(det, 'RUTDoc', ruts.normalizar(d.rut))
        sub(det, 'RznSoc', texto(d.razon_social, 50))
        if d.referencia_tipo and d.referencia_folio:
            sub(det, 'TpoDocRef', d.referencia_tipo)
            sub(det, 'FolioDocRef', d.referencia_folio)
        if d.exento:
            sub(det, 'MntExe', d.exento)
        if d.neto or d.iva or d.iva_uso_comun or d.iva_no_recuperable:
            sub(det, 'MntNeto', d.neto)
            sub(det, 'MntIVA', d.iva)
        for cod, monto in d.iva_no_recuperable:
            nr = sub(det, 'IVANoRec')
            sub(nr, 'CodIVANoRec', cod)
            sub(nr, 'MntIVANoRec', monto)
        if d.iva_uso_comun:
            sub(det, 'IVAUsoComun', d.iva_uso_comun)
        for cod, tasa, monto in d.otros_impuestos:
            oi = sub(det, 'OtrosImp')
            sub(oi, 'CodImp', cod)
            sub(oi, 'TasaImp', numero(tasa))
            sub(oi, 'MntImp', monto)
        if d.iva_retenido_total:
            sub(det, 'IVARetTotal', d.iva_retenido_total)
        sub(det, 'MntTotal', d.monto_total())

    return _firmar_y_cerrar(raiz, envio_libro, certificado, momento, 'LibroCompraVenta')


def libro_guias(caratula, detalles, certificado, momento=None):
    """El LibroGuia firmado. Solo admite TipoLibro ESPECIAL y lleva FolioNotificacion."""
    if not detalles:
        raise ErrorDTE('El libro de guías no tiene guías.')
    if caratula.folio_notificacion is None:
        raise ErrorDTE('El libro de guías necesita el folio de notificación.')
    momento = (momento or datetime.now()).replace(microsecond=0)
    raiz = _raiz('LibroGuia', 'LibroGuia_v10.xsd')
    envio_libro = sub(raiz, 'EnvioLibro', ID='LibroGuias')
    _caratula(envio_libro, caratula)

    vigentes = [d for d in detalles if not d.anulado]
    ventas = [d for d in vigentes if d.tipo_traslado == 1]
    resumen = sub(envio_libro, 'ResumenPeriodo')
    folios_anulados = sum(1 for d in detalles if d.anulado == 1)
    guias_anuladas = sum(1 for d in detalles if d.anulado == 2)
    if folios_anulados:
        sub(resumen, 'TotFolAnulado', folios_anulados)
    if guias_anuladas:
        sub(resumen, 'TotGuiaAnulada', guias_anuladas)
    sub(resumen, 'TotGuiaVenta', len(ventas))
    sub(resumen, 'TotMntGuiaVta', sum(d.monto_total() for d in ventas))
    otros = []
    for d in vigentes:
        if d.tipo_traslado != 1 and d.tipo_traslado not in otros:
            otros.append(d.tipo_traslado)
    for t in otros:
        ds = [d for d in vigentes if d.tipo_traslado == t]
        tt = sub(resumen, 'TotTraslado')
        sub(tt, 'TpoTraslado', t)
        sub(tt, 'CantGuia', len(ds))
        sub(tt, 'MntGuia', sum(d.monto_total() for d in ds))

    for d in detalles:
        det = sub(envio_libro, 'Detalle')
        sub(det, 'Folio', d.folio)
        if d.anulado:
            sub(det, 'Anulado', d.anulado)
        sub(det, 'TpoOper', d.tipo_traslado)
        sub(det, 'FchDoc', d.fecha.isoformat())
        sub(det, 'RUTDoc', ruts.normalizar(d.rut))
        sub(det, 'RznSoc', texto(d.razon_social, 50))
        if d.neto:
            sub(det, 'MntNeto', d.neto)
            sub(det, 'TasaImp', numero(d.tasa))
            sub(det, 'IVA', d.iva)
        sub(det, 'MntTotal', d.monto_total())
        if d.referencia_tipo and d.referencia_folio:
            sub(det, 'TpoDocRef', d.referencia_tipo)
            sub(det, 'FolioDocRef', d.referencia_folio)
            if d.referencia_fecha:
                sub(det, 'FchDocRef', d.referencia_fecha.isoformat())

    return _firmar_y_cerrar(raiz, envio_libro, certificado, momento, 'LibroGuia')
