"""Conector SII · Libros contables (27-10-2026): baja el Registro de Compras y Ventas del SII con el
certificado de la empresa y lo deja como una carga de Contabilidad, igual que si se hubiera subido
el CSV a mano (finanzas/importador.py). La carga queda en borrador para revisarla, salvo que la
empresa elija confirmarla sola.

El SII no publica una API para el RCV: se usan los servicios de su propia página
(www4.sii.cl/consdcvinternetui, "facadeService"). Lo que dice este módulo de ellos sale de lo que
publica la comunidad y de una prueba del 27-10-2026 (responde 401 a una sesión inválida). [NV]
quiere decir "no verificado con un certificado real": se confirma con el primer cliente.

    [NV] La sesión es la misma del envío de DTE (semilla firmada → token de palena), pasada en
         `metaData.conversationId` y en la cookie TOKEN (más RUT_NS/DV_NS con la empresa).
    [NV] El cuerpo es {"metaData": {namespace, conversationId, transactionId, page}, "data": {...}}
         con rutEmisor, dvEmisor, ptributario (AAAAMM), estadoContab, operacion y codTipoDoc.
    [NV] getResumen devuelve en `data` una lista de resúmenes por tipo de documento
         (rsmnTipoDocInteger, rsmnTotDoc…) y getDetalleCompra/getDetalleVenta una lista de
         documentos (detTipoDoc, detRutDoc, detDvDoc, detRznSoc, detNroDoc, detFchDoc, detMntExe,
         detMntNeto, detMntIVA, detMntIVANoRec, detMntTotal). `respEstado.codRespuesta` 0 es OK.
    [NV] Hay reportes (2024) de que el SII pide reCAPTCHA en estos servicios: si lo pide, se avisa y
         se ofrece la carga manual.
"""
import csv
import io
from datetime import date

import requests
from django.utils import timezone

from apps.finanzas import constantes as fc

from .servicio import ErrorConector

URL = 'https://www4.sii.cl/consdcvinternetui/services/data/facadeService/'
NAMESPACE = 'cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/'
TIMEOUT = 60
CONFIG_POR_DEFECTO = {'libros': ['compras', 'ventas'], 'automatico': False, 'confirmar_solo': False}
LIBROS = {'compras': ('COMPRA', fc.LIBRO_COMPRAS), 'ventas': ('VENTA', fc.LIBRO_VENTAS)}
ENLACE = '/app/contabilidad/documentos'
MSG_SESION = ('El SII no aceptó la sesión del certificado para el Registro de Compras y Ventas. Revise que el '
              'certificado esté vigente y que su titular tenga acceso a la empresa en sii.cl.')
MSG_CAPTCHA = ('El SII está pidiendo una verificación (reCAPTCHA) para descargar el Registro de Compras y Ventas: '
               'por ahora súbalo a mano en Contabilidad › Documentos.')


# ── Requisitos y conexión ─────────────────────────────────────────────────────────────────

def _certificado(org):
    from apps.dte.servicio import certificado_activo
    return certificado_activo(org)


def _rut_valido(org):
    from apps.dte.nucleo.rut import valido
    return bool(org.rut) and valido(org.rut)


def requisitos(org):
    falta = []
    if not _certificado(org):
        falta.append('el certificado digital de quien firma por la empresa (se sube en Ajustes › Empresas › '
                     'Facturación electrónica)')
    if not _rut_valido(org):
        falta.append('el RUT de la empresa (Ajustes › Empresas › Datos y logo)')
    return falta


def _token(org):
    """La sesión del SII con el certificado de la empresa (producción: el RCV es el real)."""
    from apps.dte import sii
    from apps.dte.nucleo import ErrorDTE
    try:
        cert = _certificado(org).cargar()
        return sii.ClienteSII(cert, sii.PRODUCCION).token(), cert
    except ErrorDTE as e:
        raise ErrorConector(f'El SII no dio sesión con el certificado: {e}')


def conectar(conexion, datos):
    org = conexion.organization
    falta = requisitos(org)
    if falta:
        raise ErrorConector('Para conectar falta ' + '; '.join(falta) + '.')
    _, cert = _token(org)
    conexion.cuenta = {'rut': org.rut, 'titular': cert.nombre}


def validar_config(config):
    limpia = {}
    if 'libros' in config:
        libros = [x for x in (config.get('libros') or []) if x in LIBROS]
        if not libros:
            raise ErrorConector('Elija al menos un libro: compras o ventas.')
        limpia['libros'] = libros
    for clave in ('automatico', 'confirmar_solo'):
        if clave in config:
            limpia[clave] = bool(config[clave])
    return limpia


# ── Conversación con el SII ───────────────────────────────────────────────────────────────

def _pedir(metodo, token, org, data):
    """Una llamada al facadeService. Devuelve la lista de `data` (vacía si no hay documentos)."""
    from apps.dte.nucleo.rut import partes
    rut, dv = partes(org.rut)
    cuerpo = {'metaData': {'namespace': NAMESPACE + metodo, 'conversationId': token, 'transactionId': '0', 'page': None},
              'data': {'rutEmisor': rut, 'dvEmisor': dv, **data}}
    try:
        r = requests.post(URL + metodo, json=cuerpo, timeout=TIMEOUT,
                          headers={'Cookie': f'TOKEN={token}; RUT_NS={rut}; DV_NS={dv}',
                                   'Content-Type': 'application/json', 'Accept': 'application/json'})
    except requests.RequestException:
        raise ErrorConector('No se pudo conectar con el SII. Puede estar caído: se intenta de nuevo más tarde.')
    texto = r.text or ''
    if 'captcha' in texto.lower():
        raise ErrorConector(MSG_CAPTCHA)
    if r.status_code in (401, 403) or texto.lstrip().lower().startswith('<html'):
        raise ErrorConector(MSG_SESION)
    if r.status_code >= 400:
        raise ErrorConector(f'El SII respondió con un error ({r.status_code}) al pedir el Registro de Compras y Ventas.')
    try:
        respuesta = r.json()
    except ValueError:
        raise ErrorConector('El SII respondió algo que no se pudo leer como datos.')
    estado = respuesta.get('respEstado') or {}
    codigo = str(estado.get('codRespuesta', 0))
    if codigo != '0':
        glosa = estado.get('msgeRespuesta') or estado.get('codError') or 'sin detalle'
        if 'captcha' in str(glosa).lower():
            raise ErrorConector(MSG_CAPTCHA)
        if 'no existen' in str(glosa).lower() or 'sin datos' in str(glosa).lower():
            return []
        raise ErrorConector(f'El SII no entregó el Registro de Compras y Ventas ({glosa}).')
    datos = respuesta.get('data')
    if isinstance(datos, list):
        return datos
    return []


def _tipos(token, org, operacion, periodo):
    """Los tipos de documento con movimiento en el período, según el resumen del SII."""
    resumen = _pedir('getResumen', token, org, {'ptributario': periodo, 'estadoContab': 'REGISTRO',
                                                'operacion': operacion, 'busquedaInicial': True})
    tipos = []
    for r in resumen:
        tipo = _primero(r, 'rsmnTipoDocInteger', 'rsmnCodigo', 'dcvCodigo', 'tipoDoc')
        total = _primero(r, 'rsmnTotDoc', 'totalDocumentos')
        if tipo is not None and str(total if total is not None else 1) != '0':
            tipos.append(int(tipo))
    return tipos


# ── Del formato del SII al CSV que lee el importador ──────────────────────────────────────

def _primero(registro, *claves):
    for k in claves:
        if k in registro and registro[k] not in (None, ''):
            return registro[k]
    return None


def _fecha(valor):
    """[NV] El SII entrega 'dd/mm/aaaa' o 'aaaa-mm-dd' (a veces con hora)."""
    v = str(valor or '').strip().split(' ')[0].split('T')[0]
    if len(v) == 10 and v[4] == '-':
        return f'{v[8:10]}/{v[5:7]}/{v[0:4]}'
    return v


def _rut(registro):
    """El RUT del documento: con su dígito en otro campo (detRutDoc + detDvDoc) o completo."""
    rut = _primero(registro, 'detRutDoc', 'rutDoc', 'detRut', 'rutProveedor', 'rutCliente')
    if rut is None:
        return ''
    rut = str(rut).strip()
    if '-' in rut:
        return rut
    dv = _primero(registro, 'detDvDoc', 'dvDoc', 'dv')
    return f'{rut}-{dv}' if dv is not None else rut


def _monto(registro, *claves):
    v = _primero(registro, *claves)
    try:
        return str(int(round(float(v)))) if v is not None else '0'
    except (TypeError, ValueError):
        return '0'


def filas_csv(registros, libro):
    """El CSV (separado por ;) con los encabezados que entiende finanzas/importador.py."""
    rut_col = 'RUT Proveedor' if libro == fc.LIBRO_COMPRAS else 'Rut cliente'
    iva_col = 'Monto IVA Recuperable' if libro == fc.LIBRO_COMPRAS else 'Monto IVA'
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=';')
    w.writerow(['Tipo Doc', rut_col, 'Razon Social', 'Folio', 'Fecha Docto', 'Monto Exento', 'Monto Neto', iva_col,
                'Monto IVA No Recuperable', 'Monto Total'])
    for r in registros:
        w.writerow([
            _primero(r, 'detTipoDoc', 'tipoDoc', 'dcvTipoDoc') or '',
            _rut(r),
            str(_primero(r, 'detRznSoc', 'razonSocial', 'detRazonSocial') or '').strip(),
            _primero(r, 'detNroDoc', 'folio', 'detFolio') or '',
            _fecha(_primero(r, 'detFchDoc', 'fechaDocto', 'detFecha')),
            _monto(r, 'detMntExe', 'montoExento'),
            _monto(r, 'detMntNeto', 'montoNeto'),
            _monto(r, 'detMntIVA', 'montoIva', 'detMntIvaRecuperable'),
            _monto(r, 'detMntIVANoRec', 'montoIvaNoRecuperable'),
            _monto(r, 'detMntTotal', 'montoTotal'),
        ])
    return salida.getvalue().encode('utf-8')


# ── Sincronizar ───────────────────────────────────────────────────────────────────────────

def _periodos(opciones, hoy):
    """El período pedido o, por defecto, el mes en curso (y el anterior en los primeros 12 días,
    cuando todavía llegan documentos del mes cerrado y vence el F29)."""
    if opciones.get('periodo'):
        p = str(opciones['periodo']).replace('-', '')
        if len(p) != 6 or not p.isdigit() or not 1 <= int(p[4:]) <= 12:
            raise ErrorConector('El período va como AAAAMM, por ejemplo 202610.')
        return [p]
    actual = f'{hoy.year}{hoy.month:02d}'
    if hoy.day > 12:
        return [actual]
    anterior = date(hoy.year - 1, 12, 1) if hoy.month == 1 else date(hoy.year, hoy.month - 1, 1)
    return [f'{anterior.year}{anterior.month:02d}', actual]


def sincronizar(conexion, opciones, usuario):
    from apps.finanzas import importador
    from apps.finanzas.models import Carga
    org = conexion.organization
    falta = requisitos(org)
    if falta:
        raise ErrorConector('Falta ' + '; '.join(falta) + '.')
    config = {**CONFIG_POR_DEFECTO, **conexion.config}
    libros = [x for x in (opciones.get('libros') or config['libros']) if x in LIBROS]
    periodos = _periodos(opciones, timezone.localdate())
    token, _ = _token(org)
    cargas = []
    for libro in libros:
        operacion, libro_fin = LIBROS[libro]
        metodo = 'getDetalleCompra' if operacion == 'COMPRA' else 'getDetalleVenta'
        for periodo in periodos:
            registros = []
            for tipo in _tipos(token, org, operacion, periodo):
                for r in _pedir(metodo, token, org, {'ptributario': periodo, 'estadoContab': 'REGISTRO',
                                                    'operacion': operacion, 'codTipoDoc': tipo}):
                    r.setdefault('detTipoDoc', tipo)
                    registros.append(r)
            if not registros:
                continue  # nada en el período: no se crea una carga vacía
            nombre = f'SII RCV {libro} {periodo}.csv'
            # Una sincronización nueva reemplaza la carga en borrador anterior del mismo libro y período.
            Carga.objects.filter(organization=org, nombre_archivo=nombre, estado=Carga.BORRADOR).delete()
            contenido = filas_csv(registros, libro_fin)
            try:
                if config.get('confirmar_solo'):
                    carga = importador.importar(org, contenido, nombre, libro_fin, usuario)
                else:
                    carga = importador.previsualizar(org, contenido, nombre, libro_fin, usuario)
            except importador.ArchivoNoReconocido as e:
                raise ErrorConector(f'Lo que entregó el SII no se pudo leer: {e}')
            cargas.append({'libro': libro, 'periodo': periodo, 'carga_id': carga.id, 'filas': carga.filas,
                           'nuevos': carga.nuevos, 'ya_estaban': carga.duplicados,
                           'errores': len(carga.errores or []), 'estado': carga.estado})
    return {'cargas': cargas, 'periodos': periodos, 'libros': libros, 'enlace': ENLACE}


def toca_correr(conexion, ahora):
    """Una vez al día, desde las 7:00 de Chile."""
    local = timezone.localtime(ahora)
    if local.hour < 7:
        return False
    ultima = conexion.ultima_sincronizacion
    return not ultima or timezone.localtime(ultima).date() < local.date()
