"""
Registro de conectores — construye el contexto del agente a partir de
todos los sistemas conectados a una organización.
"""
import json
from datetime import datetime, date
from typing import Optional


def get_business_model(organization) -> dict:
    """
    Grafo del 'modelo vivo' del negocio a partir del schema_cache de los sistemas
    conectados: entidades (tablas con columnas, tipo y conteo) y relaciones (FKs).
    No golpea la base en vivo — usa el cache de la última sincronización.
    """
    from apps.organizations.models import SystemConnection
    SRC_COLORS = {'postgresql': '#34D399', 'mssql': '#F87171', 'odoo': '#A78BFA', 'csv': '#F59E0B'}
    connections = SystemConnection.objects.filter(organization=organization, is_active=True)

    sources, entities, edges = [], [], []
    synced = False
    for conn in connections:
        sc = conn.schema_cache or {}
        sources.append({
            'id': conn.id, 'name': conn.name, 'type': conn.connector_type,
            'color': SRC_COLORS.get(conn.connector_type, '#586AD0'),
            'synced_at': conn.last_synced_at.isoformat() if conn.last_synced_at else None,
        })
        schema = sc.get('schema') or {}
        counts = sc.get('counts') or {}
        for table in (sc.get('tables') or [])[:20]:
            cols = schema.get(table, [])
            entities.append({
                'id': f'{conn.id}:{table}',
                'table': table,
                'source_id': conn.id,
                'source': conn.name,
                'color': SRC_COLORS.get(conn.connector_type, '#586AD0'),
                'count': counts.get(table),
                'fields': [{'name': c.get('column'), 'type': c.get('type')} for c in cols][:30],
            })
            synced = True
        for rel in (sc.get('relations') or []):
            edges.append({
                'from': f'{conn.id}:{rel.get("from_table")}',
                'to': f'{conn.id}:{rel.get("to_table")}',
                'from_column': rel.get('from_column'),
                'to_column': rel.get('to_column'),
            })

    return {'sources': sources, 'entities': entities, 'edges': edges, 'synced': synced}


def get_connections_context(organization, allowed_ids=None) -> Optional[str]:
    """
    Retorna un bloque de contexto con los sistemas activos de la org.
    Retorna None si no hay conexiones activas.

    `allowed_ids` es el alcance del agente según sus Espacios: `None` es sin
    restricción. Sin este filtro el bloque nombraba, con su esquema completo, los
    sistemas de Espacios donde el agente no entra — el agente no podía consultarlos
    (eso ya lo cortaba `allowed_ids` en las herramientas) pero sí sabía que existían
    y cómo se llamaban sus tablas.
    """
    from apps.organizations.models import SystemConnection
    connections = SystemConnection.objects.filter(
        organization=organization, is_active=True
    )
    if allowed_ids is not None:
        connections = connections.filter(id__in=allowed_ids)
    if not connections.exists():
        return None

    parts = []
    for conn in connections:
        ctx = _build_connection_context(conn)
        if ctx:
            parts.append(ctx)

    return '\n\n'.join(parts) if parts else None


def test_connection(connection) -> dict:
    """Prueba una conexión y retorna {success, error, tables_count}."""
    try:
        if connection.connector_type == 'odoo':
            return _test_odoo(connection)
        elif connection.connector_type in ('mssql', 'postgresql'):
            return _test_sql(connection)
        elif connection.connector_type == 'csv':
            return {'success': True, 'message': 'Archivo cargado correctamente'}
        return {'success': False, 'error': 'Tipo de conector no soportado'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def sync_schema(connection) -> dict:
    """
    Descubre el esquema del sistema y lo guarda en schema_cache.
    Retorna el schema descubierto.
    """
    from django.utils import timezone
    try:
        if connection.connector_type == 'odoo':
            schema = _discover_odoo_schema(connection)
        elif connection.connector_type in ('mssql', 'postgresql'):
            schema = _discover_sql_schema(connection)
        else:
            return {}

        connection.schema_cache = schema
        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['schema_cache', 'last_synced_at'])
        return schema
    except Exception as e:
        return {'error': str(e)}


# ── Odoo ──────────────────────────────────────────────────────────────────────

def _test_odoo(connection) -> dict:
    from services.odoo_client import OdooClient, OdooConnectionError
    cfg = connection.get_config()
    try:
        client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
        uid = client.authenticate()
        return {'success': True, 'uid': uid}
    except OdooConnectionError as e:
        return {'success': False, 'error': str(e)}


def _discover_odoo_schema(connection) -> dict:
    from services.odoo_client import OdooClient
    cfg = connection.get_config()
    client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
    client.authenticate()

    key_models = [
        'sale.order', 'sale.order.line', 'account.invoice', 'account.move',
        'stock.quant', 'product.product', 'product.template',
        'res.partner', 'purchase.order', 'hr.employee',
        'account.analytic.line', 'mrp.production',
    ]
    available = []
    for model in key_models:
        try:
            count = client.search_count(model)
            available.append({'model': model, 'records': count})
        except Exception:
            pass

    return {'type': 'odoo', 'models': available}


def _build_odoo_context(connection) -> str:
    from services.odoo_client import OdooClient, OdooConnectionError
    cfg = connection.get_config()
    schema = connection.schema_cache

    lines = [f'## Sistema: {connection.name} (Odoo)']

    if schema and schema.get('models'):
        lines.append('Módulos disponibles:')
        for m in schema['models']:
            lines.append(f"  - {m['model']}: {m['records']} registros")
    else:
        lines.append('Esquema no sincronizado aún. Usa /sync para descubrir módulos.')

    # Obtener muestra de ventas recientes si está disponible
    try:
        client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
        orders = client.search_read(
            'sale.order',
            domain=[['state', 'in', ['sale', 'done']]],
            fields=['name', 'partner_id', 'amount_total', 'date_order', 'state'],
            limit=5,
            order='date_order desc',
        )
        if orders:
            lines.append('\nÚltimas órdenes de venta:')
            for o in orders:
                lines.append(
                    f"  {o['name']} | {o['partner_id'][1] if o['partner_id'] else '-'} "
                    f"| ${o['amount_total']:,.0f} | {o['date_order'][:10]}"
                )
    except Exception:
        pass

    return '\n'.join(lines)


# ── SQL (MSSQL / PostgreSQL / SAP B1) ─────────────────────────────────────────

def _test_sql(connection) -> dict:
    from services.sql_client import SQLClient
    cfg = connection.get_config()
    client = SQLClient(connection.connector_type, cfg)
    return client.test_connection()


def _discover_sql_schema(connection) -> dict:
    from services.sql_client import SQLClient
    cfg = connection.get_config()
    with SQLClient(connection.connector_type, cfg) as client:
        tables = client.list_tables()
        schema = {}
        counts = {}
        # Describe solo las primeras 20 tablas para no saturar
        for table in tables[:20]:
            try:
                schema[table] = client.describe_table(table)
            except Exception:
                schema[table] = []
            counts[table] = client.count_rows(table)
        try:
            relations = client.list_relations()
        except Exception:
            relations = []
        return {'type': connection.connector_type, 'tables': tables,
                'schema': schema, 'counts': counts, 'relations': relations}


def _build_sql_context(connection) -> str:
    schema = connection.schema_cache
    type_label = 'SAP Business One / SQL Server' if connection.connector_type == 'mssql' else 'PostgreSQL'
    lines = [f'## Sistema: {connection.name} ({type_label})']

    if schema and schema.get('tables'):
        tables = schema['tables']
        lines.append(f'Tablas disponibles ({len(tables)} total):')
        for t in tables[:15]:
            cols = schema.get('schema', {}).get(t, [])
            col_names = ', '.join(c['column'] for c in cols[:5])
            suffix = '...' if len(cols) > 5 else ''
            lines.append(f'  - {t}: {col_names}{suffix}')
        if len(tables) > 15:
            lines.append(f'  ... y {len(tables) - 15} tablas más')
    else:
        lines.append('Esquema no sincronizado. Conecta y sincroniza para ver las tablas disponibles.')

    return '\n'.join(lines)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _build_connection_context(connection) -> Optional[str]:
    try:
        if connection.connector_type == 'odoo':
            return _build_odoo_context(connection)
        elif connection.connector_type in ('mssql', 'postgresql'):
            return _build_sql_context(connection)
        elif connection.connector_type == 'csv':
            return _build_csv_context(connection)
    except Exception:
        return None


def _build_csv_context(connection) -> str:
    schema = connection.schema_cache
    lines = [f'## Sistema: {connection.name} (Excel/CSV)']
    if schema.get('columns'):
        lines.append(f"Columnas: {', '.join(schema['columns'])}")
    if schema.get('rows'):
        lines.append(f"Filas: {schema['rows']}")
    if schema.get('sample'):
        lines.append(f"Muestra: {json.dumps(schema['sample'][:3], ensure_ascii=False)}")
    return '\n'.join(lines)


# ── Dashboard KPIs ────────────────────────────────────────────────────────────

def get_dashboard_kpis(organization) -> list:
    """
    Retorna KPIs en vivo por cada sistema conectado a la organización.
    Usado por el endpoint /api/v1/organizations/dashboard/
    """
    from apps.organizations.models import SystemConnection
    connections = SystemConnection.objects.filter(organization=organization, is_active=True)
    results = []
    now_str = datetime.now().strftime('%H:%M')

    for conn in connections:
        entry = {
            'connection_id': conn.id,
            'name': conn.name,
            'connector_type': conn.connector_type,
            'status': 'ok',
            'last_updated': now_str,
            'kpis': [],
        }
        try:
            if conn.connector_type == 'odoo':
                entry['kpis'] = _kpis_odoo(conn)
            elif conn.connector_type in ('mssql', 'postgresql'):
                entry['kpis'] = _kpis_sql(conn)
            elif conn.connector_type == 'csv':
                entry['kpis'] = _kpis_csv(conn)
            elif conn.connector_type == 'google_drive':
                # Drive no tiene KPIs de negocio: lo que importa es cuantos documentos
                # quedaron disponibles para la IA. Sin esto el panel decia
                # "Sin datos — sincroniza el sistema" con los documentos ya al dia.
                from apps.organizations.models import CompanyDocument
                n = CompanyDocument.objects.filter(
                    organization=organization, source='drive_sync',
                ).count()
                entry['kpis'] = [{
                    'label': 'Documentos disponibles',
                    'value': str(n),
                    'hint': 'los lee la IA en cada respuesta' if n else 'vuelve a elegir los archivos',
                }]
        except Exception as e:
            entry['status'] = 'error'
            entry['error'] = str(e)
        results.append(entry)
    return results


def _kpis_odoo(connection) -> list:
    from services.odoo_client import OdooClient
    cfg = connection.get_config()
    client = OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])
    client.authenticate()

    today = date.today()
    first_day = today.replace(day=1).strftime('%Y-%m-%d')
    kpis = []

    # Ventas del mes
    try:
        orders_mes = client.search_read(
            'sale.order',
            domain=[['state', 'in', ['sale', 'done']], ['date_order', '>=', first_day]],
            fields=['amount_total'], limit=200,
        )
        total_mes = sum(o['amount_total'] for o in orders_mes)
        kpis.append({'label': 'Ventas del mes', 'value': f'${total_mes:,.0f}', 'count': len(orders_mes)})
    except Exception:
        pass

    # Órdenes abiertas
    try:
        abiertas = client.search_count('sale.order', [['state', '=', 'sale']])
        kpis.append({'label': 'Órdenes abiertas', 'value': str(abiertas)})
    except Exception:
        pass

    # Clientes activos
    try:
        clientes = client.search_count('res.partner', [['customer_rank', '>', 0], ['active', '=', True]])
        kpis.append({'label': 'Clientes activos', 'value': str(clientes)})
    except Exception:
        pass

    # Facturas pendientes
    try:
        pendientes = client.search_count('account.move', [['state', '=', 'posted'], ['payment_state', '=', 'not_paid']])
        if pendientes > 0:
            kpis.append({'label': 'Facturas por cobrar', 'value': str(pendientes), 'alert': True})
    except Exception:
        pass

    return kpis


def _kpis_sql(connection) -> list:
    schema = connection.schema_cache or {}
    kpis = []
    tables = schema.get('tables') or []
    counts = schema.get('counts') or {}

    if not tables:
        kpis.append({'label': 'Estado', 'value': 'Sincroniza para ver datos'})
        return kpis

    # KPIs reales: registros por las tablas con más volumen (conteos del último sync).
    counted = [(t, counts[t]) for t in tables if counts.get(t) is not None]
    counted.sort(key=lambda x: x[1], reverse=True)
    for table, n in counted[:4]:
        kpis.append({'label': table, 'value': f'{n:,}'.replace(',', '.'), 'count': n})

    if not counted:
        kpis.append({'label': 'Tablas disponibles', 'value': str(len(tables))})

    kpis.append({'label': 'Tablas', 'value': str(len(tables))})
    if connection.last_synced_at:
        kpis.append({'label': 'Último sync', 'value': connection.last_synced_at.strftime('%d/%m %H:%M')})
    return kpis


def _kpis_csv(connection) -> list:
    schema = connection.schema_cache
    kpis = []
    if schema.get('rows'):
        kpis.append({'label': 'Filas', 'value': str(schema['rows'])})
    if schema.get('columns'):
        kpis.append({'label': 'Columnas', 'value': str(len(schema['columns']))})
    return kpis
