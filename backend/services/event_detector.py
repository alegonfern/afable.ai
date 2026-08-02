"""
Detección de eventos sobre las conexiones (disparador 'event' de Automation).

En cada revisión se observa el estado actual del sistema conectado y se compara
contra el snapshot guardado en Automation.event_state. La PRIMERA revisión solo
inicializa el snapshot (no dispara) — así una automatización recién creada no
reporta como "nuevo" todo lo que ya existía. Excepción: connection_down dispara
también en la primera revisión si la conexión ya está caída (eso sí es urgente).

Eventos soportados (Automation.EVENT_TYPES):
- new_table:        aparece una tabla (SQL) o un modelo (Odoo) que no estaba.
- new_rows:         sube el conteo de filas de la tabla en event_config['table'].
- connection_down:  la conexión pasa de arriba a caída.
"""
import logging

logger = logging.getLogger(__name__)


def check_event(automation) -> dict:
    """
    Evalúa el evento de una Automation y actualiza su snapshot (event_state,
    persistido por el caller junto al resto de la Automation).
    Devuelve {'fired': bool, 'details': str, 'error': str}.
    """
    conn = automation.connection
    if conn is None:
        return {'fired': False, 'details': '', 'error': 'La automatización no tiene conexión asociada.'}

    checker = {
        'new_table': _check_new_table,
        'new_rows': _check_new_rows,
        'connection_down': _check_connection_down,
    }.get(automation.event_type)
    if checker is None:
        return {'fired': False, 'details': '', 'error': f'Tipo de evento desconocido: {automation.event_type}'}

    try:
        return checker(automation, conn)
    except Exception as e:
        logger.exception('Automation %s: fallo revisando evento %s', automation.id, automation.event_type)
        return {'fired': False, 'details': '', 'error': str(e)[:500]}


# ── Observadores por conector ─────────────────────────────────────────────────

def _observe_tables(conn) -> list:
    """Nombres de tablas (SQL) o modelos con datos (Odoo) visibles ahora."""
    cfg = conn.get_config()
    if conn.connector_type == 'odoo':
        from services.odoo_client import OdooClient
        client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
        client.authenticate()
        rows = client.search_read('ir.model', fields=['model'], limit=10000)
        return sorted(r['model'] for r in rows)
    from services.sql_client import SQLClient
    with SQLClient(conn.connector_type, cfg) as client:
        return sorted(client.list_tables())


def _observe_count(conn, table: str) -> int:
    cfg = conn.get_config()
    if conn.connector_type == 'odoo':
        from services.odoo_client import OdooClient
        client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
        client.authenticate()
        return client.search_count(table)
    from services.sql_client import SQLClient
    with SQLClient(conn.connector_type, cfg) as client:
        return client.count_rows(table)


# ── Checkers ──────────────────────────────────────────────────────────────────

def _check_new_table(automation, conn) -> dict:
    observed = _observe_tables(conn)
    state = automation.event_state or {}
    known = state.get('tables')

    automation.event_state = {'tables': observed}
    if known is None:  # primera revisión: solo snapshot
        return {'fired': False, 'details': '', 'error': ''}

    new = sorted(set(observed) - set(known))
    if not new:
        return {'fired': False, 'details': '', 'error': ''}
    kind = 'modelos' if conn.connector_type == 'odoo' else 'tablas'
    return {
        'fired': True,
        'details': f'Se detectaron {len(new)} {kind} nuevas en «{conn.name}»: ' + ', '.join(new[:20])
                   + ('…' if len(new) > 20 else ''),
        'error': '',
    }


def _check_new_rows(automation, conn) -> dict:
    table = (automation.event_config or {}).get('table', '').strip()
    if not table:
        return {'fired': False, 'details': '', 'error': 'Falta la tabla a vigilar (event_config.table).'}

    count = _observe_count(conn, table)
    state = automation.event_state or {}
    last = state.get('count')

    automation.event_state = {'count': count, 'table': table}
    if last is None or state.get('table') != table:  # primera revisión (o cambió la tabla)
        return {'fired': False, 'details': '', 'error': ''}

    if count > last:
        return {
            'fired': True,
            'details': f'{count - last} filas nuevas en «{table}» de «{conn.name}» (de {last} a {count}).',
            'error': '',
        }
    return {'fired': False, 'details': '', 'error': ''}


def _check_connection_down(automation, conn) -> dict:
    from services.connector_registry import test_connection
    result = test_connection(conn)
    up = bool(result.get('success'))
    state = automation.event_state or {}
    was_up = state.get('up')

    automation.event_state = {'up': up}
    # Dispara al pasar de arriba→caída, o si ya nace caída (was_up is None).
    if not up and was_up is not False:
        return {
            'fired': True,
            'details': f'La conexión «{conn.name}» está caída: {result.get("error", "sin detalle")}',
            'error': '',
        }
    return {'fired': False, 'details': '', 'error': ''}
