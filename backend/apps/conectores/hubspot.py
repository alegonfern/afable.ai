"""El conector de HubSpot (27-10-2026): trae las empresas y los contactos del CRM como clientes de
Afable, y los negocios ganados como cotizaciones de venta en borrador, listas para revisar.

Se conecta con el token de una "app privada" de HubSpot (Configuración › Integraciones › Apps
privadas), con permiso de lectura de empresas, contactos y negocios. Lo que se trae se recuerda en
`conexion.config` (mapa_empresas, mapa_contactos, negocios) para no duplicar en la siguiente
sincronización: HubSpot no tiene dónde guardar el id de Afable ni Afable el de HubSpot.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.db import transaction

from apps.finanzas.models import Contacto

from .servicio import ErrorConector

API = 'https://api.hubapi.com'
TIMEOUT = 30
POR_PAGINA = 100
CADA = timedelta(hours=6)

CONFIG_POR_DEFECTO = {'importar_empresas': True, 'importar_contactos': True, 'negocios_a_cotizacion': True,
                      'automatico': True}
OPCIONES = tuple(CONFIG_POR_DEFECTO)


# ── La API ────────────────────────────────────────────────────────────────────

def _pedir(token, metodo, ruta, **kwargs):
    """Una llamada a HubSpot. Los errores se dicen en español, sin el detalle técnico."""
    try:
        r = requests.request(metodo, f'{API}{ruta}', headers={'Authorization': f'Bearer {token}',
                                                             'Content-Type': 'application/json'},
                             timeout=TIMEOUT, **kwargs)
    except requests.RequestException:
        raise ErrorConector('No se pudo conectar con HubSpot. Revise la conexión e intente de nuevo.')
    if r.status_code == 401:
        raise ErrorConector('HubSpot no reconoce ese token: revíselo o genere uno nuevo en su app privada.')
    if r.status_code == 403:
        raise ErrorConector('El token no tiene permiso para leer esto en HubSpot: en la app privada, agregue '
                            'los permisos de lectura de empresas, contactos y negocios (crm.objects.*.read).')
    if r.status_code == 429:
        espera = r.headers.get('Retry-After')
        raise ErrorConector('HubSpot pidió esperar antes de seguir (límite de consultas). Intente de nuevo '
                            f'{"en " + espera + " segundos" if espera else "en unos minutos"}.')
    if r.status_code >= 500:
        raise ErrorConector('HubSpot no está respondiendo. Intente de nuevo en unos minutos.')
    if r.status_code >= 400:
        raise ErrorConector(f'HubSpot rechazó la consulta ({r.status_code}).')
    try:
        return r.json()
    except ValueError:
        raise ErrorConector('HubSpot respondió algo que no se pudo leer.')


def _paginas(token, metodo, ruta, base, clave):
    """Recorre las páginas de un listado o una búsqueda (paging.next.after)."""
    despues = None
    while True:
        datos = {**base, 'limit': POR_PAGINA}
        if despues:
            datos['after'] = despues
        r = _pedir(token, metodo, ruta, **{clave: datos})
        yield from r.get('results') or []
        despues = ((r.get('paging') or {}).get('next') or {}).get('after')
        if not despues:
            return


# ── La interfaz de los conectores ─────────────────────────────────────────────

def conectar(conexion, datos):
    token = str((datos or {}).get('token') or '').strip()
    if not token:
        raise ErrorConector('Pegue el token de acceso de su app privada de HubSpot.')
    cuenta = _pedir(token, 'GET', '/account-info/v3/details')
    conexion.guardar_secreto(token)
    conexion.cuenta = {'portal_id': cuenta.get('portalId'), 'zona_horaria': cuenta.get('timeZone', ''),
                       'moneda': cuenta.get('companyCurrency', '')}
    conexion.config = {**CONFIG_POR_DEFECTO, **(conexion.config or {})}


def validar_config(config):
    return {k: bool(v) for k, v in (config or {}).items() if k in OPCIONES}


def requisitos(org):
    return []


def toca_correr(conexion, ahora):
    return conexion.ultima_sincronizacion is None or ahora - conexion.ultima_sincronizacion >= CADA


def sincronizar(conexion, opciones, usuario):
    token = conexion.secreto
    if not token:
        raise ErrorConector('Falta el token de HubSpot: vuelva a conectar.')
    cfg = {**CONFIG_POR_DEFECTO, **(conexion.config or {})}
    org = conexion.organization
    resumen = {'empresas': {'nuevas': 0, 'actualizadas': 0}, 'contactos': {'nuevos': 0, 'actualizados': 0},
               'cotizaciones': {'nuevas': 0, 'ya_estaban': 0}, 'avisos': []}
    mapa_empresas = {str(k): v for k, v in (cfg.get('mapa_empresas') or {}).items()}
    mapa_contactos = {str(k): v for k, v in (cfg.get('mapa_contactos') or {}).items()}
    negocios = {str(k): v for k, v in (cfg.get('negocios') or {}).items()}
    try:
        if cfg['importar_empresas']:
            _empresas(token, org, mapa_empresas, resumen)
        if cfg['importar_contactos']:
            _contactos(token, org, mapa_empresas, mapa_contactos, resumen)
        if cfg['negocios_a_cotizacion']:
            _negocios(token, org, mapa_empresas, negocios, usuario, resumen)
    finally:
        # Lo que alcanzó a entrar queda recordado aunque HubSpot corte a la mitad (límite de consultas).
        conexion.config = {**(conexion.config or {}), 'mapa_empresas': mapa_empresas,
                           'mapa_contactos': mapa_contactos, 'negocios': negocios}
        conexion.save(update_fields=['config', 'actualizado_en'])
    return resumen


# ── Empresas y contactos ──────────────────────────────────────────────────────

def _rut(valor):
    from apps.dte.nucleo.rut import normalizar, valido
    v = str(valor or '').strip()
    return normalizar(v) if v and valido(v) else ''


def _propiedad_rut(token):
    """El nombre interno de la propiedad de empresa donde la cuenta guarda el RUT, si la tiene."""
    try:
        datos = _pedir(token, 'GET', '/crm/v3/properties/companies')
    except ErrorConector:
        return None
    for p in datos.get('results') or []:
        nombre = str(p.get('name') or '').lower()
        if nombre == 'rut' or nombre.startswith('rut_') or nombre.endswith('_rut') or '_rut_' in nombre:
            return p['name']
    return None


def _completar(contacto, campos):
    """Llena lo que la ficha tiene vacío (lo escrito en Afable manda). Devuelve si cambió algo."""
    cambio = False
    for campo, valor in campos.items():
        valor = str(valor or '').strip()
        if valor and not getattr(contacto, campo):
            largo = contacto._meta.get_field(campo).max_length
            setattr(contacto, campo, valor[:largo] if largo else valor)
            cambio = True
    return cambio


def _empresas(token, org, mapa, resumen):
    prop_rut = _propiedad_rut(token)
    propiedades = ['name', 'domain', 'phone', 'address', 'city'] + ([prop_rut] if prop_rut else [])
    for e in _paginas(token, 'GET', '/crm/v3/objects/companies', {'properties': ','.join(propiedades)}, 'params'):
        p = e.get('properties') or {}
        nombre = str(p.get('name') or p.get('domain') or '').strip()
        if not nombre:
            continue
        rut = _rut(p.get(prop_rut)) if prop_rut else ''
        c = Contacto.objects.filter(organization=org, pk=mapa.get(str(e['id']))).first() if mapa.get(str(e['id'])) else None
        if c is None and rut:
            c = Contacto.objects.filter(organization=org, rut=rut).first()
        if c is None:
            c = Contacto.objects.filter(organization=org, razon_social__iexact=nombre).first()
        if c is None:
            c = Contacto.objects.create(organization=org, razon_social=nombre[:255], rut=rut, es_cliente=True,
                                        telefono=str(p.get('phone') or '')[:30],
                                        direccion=str(p.get('address') or '')[:255], ciudad=str(p.get('city') or '')[:80])
            resumen['empresas']['nuevas'] += 1
        else:
            cambio = _completar(c, {'rut': rut, 'telefono': p.get('phone'), 'direccion': p.get('address'),
                                    'ciudad': p.get('city')})
            if not c.es_cliente:
                c.es_cliente, cambio = True, True
            if cambio:
                c.save()
                resumen['empresas']['actualizadas'] += 1
        mapa[str(e['id'])] = c.id


def _contactos(token, org, mapa_empresas, mapa_contactos, resumen):
    base = {'properties': 'firstname,lastname,email,phone,company', 'associations': 'companies'}
    for x in _paginas(token, 'GET', '/crm/v3/objects/contacts', base, 'params'):
        p = x.get('properties') or {}
        nombre = ' '.join(s for s in (str(p.get('firstname') or '').strip(), str(p.get('lastname') or '').strip()) if s)
        nombre = nombre or str(p.get('email') or '').strip()
        if not nombre:
            continue
        asociadas = ((x.get('associations') or {}).get('companies') or {}).get('results') or []
        empresa = next((mapa_empresas[str(a['id'])] for a in asociadas if str(a.get('id')) in mapa_empresas), None)
        if empresa:
            # Una persona de una empresa: completa los datos de contacto de esa empresa.
            c = Contacto.objects.filter(organization=org, pk=empresa).first()
            if c and _completar(c, {'persona_contacto': nombre, 'email': p.get('email'), 'telefono': p.get('phone')}):
                c.save()
                resumen['contactos']['actualizados'] += 1
            continue
        # Una persona sin empresa: es un cliente en sí misma.
        previo = mapa_contactos.get(str(x['id']))
        c = Contacto.objects.filter(organization=org, pk=previo).first() if previo else None
        if c is None and p.get('email'):
            c = Contacto.objects.filter(organization=org, email__iexact=str(p['email']).strip()).first()
        if c is None:
            c = Contacto.objects.create(organization=org, razon_social=nombre[:255], email=str(p.get('email') or '')[:254],
                                        telefono=str(p.get('phone') or '')[:30], es_cliente=True)
            resumen['contactos']['nuevos'] += 1
        elif _completar(c, {'email': p.get('email'), 'telefono': p.get('phone')}):
            c.save()
            resumen['contactos']['actualizados'] += 1
        mapa_contactos[str(x['id'])] = c.id


# ── Negocios ganados → cotizaciones ───────────────────────────────────────────

def _empresa_del_negocio(token, deal_id, mapa_empresas):
    datos = _pedir(token, 'GET', f'/crm/v3/objects/deals/{deal_id}', params={'associations': 'companies'})
    for a in ((datos.get('associations') or {}).get('companies') or {}).get('results') or []:
        if str(a.get('id')) in mapa_empresas:
            return mapa_empresas[str(a['id'])]
    return None


def _monto(valor):
    try:
        return Decimal(str(valor)).quantize(Decimal('0.0001'))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _negocios(token, org, mapa_empresas, negocios, usuario, resumen):
    from apps.comercial import cambio, operaciones as op
    from apps.comercial.models import CLP, MONEDAS, VENTA, Pedido

    cuerpo = {'filterGroups': [{'filters': [{'propertyName': 'dealstage', 'operator': 'EQ', 'value': 'closedwon'}]}],
              'properties': ['dealname', 'amount', 'closedate', 'deal_currency_code']}
    for d in _paginas(token, 'POST', '/crm/v3/objects/deals/search', cuerpo, 'json'):
        deal_id = str(d['id'])
        if deal_id in negocios and Pedido.objects.filter(organization=org, pk=negocios[deal_id]).exists():
            resumen['cotizaciones']['ya_estaban'] += 1
            continue
        p = d.get('properties') or {}
        nombre = str(p.get('dealname') or f'Negocio {deal_id}').strip()
        monto = _monto(p.get('amount'))
        if not monto or monto <= 0:
            resumen['avisos'].append(f'«{nombre}» no tiene monto: no se creó cotización.')
            continue
        contacto_id = _empresa_del_negocio(token, deal_id, mapa_empresas)
        contacto = Contacto.objects.filter(organization=org, pk=contacto_id).first() if contacto_id else None
        if contacto is None:
            resumen['avisos'].append(f'«{nombre}» no está asociado a una empresa de HubSpot: no se creó cotización.')
            continue
        datos = {'referencia': f'HubSpot {deal_id}'[:60], 'notas': f'Negocio ganado en HubSpot: {nombre}.'}
        moneda = str(p.get('deal_currency_code') or CLP).upper()
        if moneda != CLP:
            tc = cambio.valor(moneda, date.today()) if moneda in dict(MONEDAS) else None
            if tc:
                datos.update({'moneda': moneda, 'tipo_cambio': str(tc)})
            else:
                resumen['avisos'].append(f'«{nombre}» está en {moneda}: quedó en pesos con el mismo monto; revíselo.')
        with transaction.atomic():
            pedido = op.crear_pedido(org, VENTA, contacto, usuario, **datos)
            op.guardar_lineas(pedido, [{'descripcion': nombre[:500], 'cantidad': 1, 'precio_unitario': str(monto)}])
        negocios[deal_id] = pedido.id
        resumen['cotizaciones']['nuevas'] += 1
