from .odoo_client import OdooClient, OdooConnectionError

ODOO_TOOLS = [
    {
        "name": "get_sales_orders",
        "description": (
            "Obtiene órdenes de venta de Odoo con totales y estado. "
            "Usa esto para preguntas sobre ventas, ingresos o pedidos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
                "state": {
                    "type": "string",
                    "enum": ["draft", "sent", "sale", "done", "cancel"],
                    "description": "'sale'=confirmado, 'done'=facturado",
                },
                "limit": {"type": "integer", "description": "Máximo registros (default 50)"},
            },
        },
    },
    {
        "name": "get_invoices",
        "description": (
            "Obtiene facturas de clientes con estado de pago. "
            "Usa esto para preguntas sobre cobros, cuentas por cobrar o facturación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
                "state": {
                    "type": "string",
                    "enum": ["draft", "posted", "cancel"],
                    "description": "'posted'=confirmada",
                },
                "payment_state": {
                    "type": "string",
                    "enum": ["not_paid", "in_payment", "paid", "partial", "reversed"],
                },
                "limit": {"type": "integer", "description": "Máximo registros (default 50)"},
            },
        },
    },
    {
        "name": "get_stock_levels",
        "description": (
            "Obtiene niveles de stock actuales por producto. "
            "Usa esto para preguntas sobre inventario, stock disponible o quiebre de stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Filtro por nombre de producto"},
                "low_stock_only": {
                    "type": "boolean",
                    "description": "Solo productos con qty_available <= virtual_available",
                },
                "limit": {"type": "integer", "description": "Máximo registros (default 50)"},
            },
        },
    },
    {
        "name": "get_customers",
        "description": (
            "Obtiene listado de clientes activos. "
            "Usa esto para preguntas sobre clientes, cuentas o contactos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Filtro por nombre"},
                "limit": {"type": "integer", "description": "Máximo registros (default 20)"},
            },
        },
    },
    {
        "name": "get_products",
        "description": (
            "Obtiene catálogo de productos con precios de venta. "
            "Usa esto para preguntas sobre productos, precios o catálogo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Filtro por nombre"},
                "limit": {"type": "integer", "description": "Máximo registros (default 50)"},
            },
        },
    },
    {
        "name": "get_purchase_orders",
        "description": (
            "Obtiene órdenes de compra a proveedores. "
            "Usa esto para preguntas sobre compras, proveedores o abastecimiento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
                "state": {
                    "type": "string",
                    "enum": ["draft", "sent", "purchase", "done", "cancel"],
                    "description": "'purchase'=confirmada",
                },
                "limit": {"type": "integer", "description": "Máximo registros (default 50)"},
            },
        },
    },
]


def execute_tool(name: str, inputs: dict, client: OdooClient) -> dict:
    try:
        match name:
            case "get_sales_orders":
                return _get_sales_orders(client, **inputs)
            case "get_invoices":
                return _get_invoices(client, **inputs)
            case "get_stock_levels":
                return _get_stock_levels(client, **inputs)
            case "get_customers":
                return _get_customers(client, **inputs)
            case "get_products":
                return _get_products(client, **inputs)
            case "get_purchase_orders":
                return _get_purchase_orders(client, **inputs)
            case _:
                return {"error": f"Herramienta desconocida: {name}"}
    except OdooConnectionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error inesperado: {str(e)}"}


def _build_date_domain(field: str, date_from: str = None, date_to: str = None) -> list:
    domain = []
    if date_from:
        domain.append((field, '>=', date_from))
    if date_to:
        domain.append((field, '<=', date_to + ' 23:59:59'))
    return domain


def _get_sales_orders(client, date_from=None, date_to=None, state=None, limit=50):
    domain = _build_date_domain('date_order', date_from, date_to)
    if state:
        domain.append(('state', '=', state))

    orders = client.search_read(
        'sale.order',
        domain=domain,
        fields=['name', 'date_order', 'partner_id', 'amount_untaxed', 'amount_tax',
                'amount_total', 'state', 'currency_id', 'user_id'],
        limit=limit,
        order='date_order desc',
    )
    total = sum(o.get('amount_total', 0) for o in orders)
    return {"count": len(orders), "total_amount": total, "orders": orders}


def _get_invoices(client, date_from=None, date_to=None, state=None, payment_state=None, limit=50):
    domain = [('move_type', '=', 'out_invoice')]
    domain += _build_date_domain('invoice_date', date_from, date_to)
    if state:
        domain.append(('state', '=', state))
    if payment_state:
        domain.append(('payment_state', '=', payment_state))

    invoices = client.search_read(
        'account.move',
        domain=domain,
        fields=['name', 'invoice_date', 'partner_id', 'amount_total',
                'amount_residual', 'state', 'payment_state', 'currency_id'],
        limit=limit,
        order='invoice_date desc',
    )
    total = sum(i.get('amount_total', 0) for i in invoices)
    pending = sum(i.get('amount_residual', 0) for i in invoices)
    return {"count": len(invoices), "total_amount": total, "pending_amount": pending, "invoices": invoices}


def _get_stock_levels(client, product_name=None, low_stock_only=False, limit=50):
    domain = [('type', '=', 'product')]
    if product_name:
        domain.append(('name', 'ilike', product_name))

    products = client.search_read(
        'product.product',
        domain=domain,
        fields=['name', 'default_code', 'qty_available', 'virtual_available',
                'uom_id', 'categ_id'],
        limit=limit,
        order='name asc',
    )

    if low_stock_only:
        products = [p for p in products if p.get('qty_available', 0) <= 0]

    return {"count": len(products), "products": products}


def _get_customers(client, name=None, limit=20):
    domain = [('customer_rank', '>', 0)]
    if name:
        domain.append(('name', 'ilike', name))

    customers = client.search_read(
        'res.partner',
        domain=domain,
        fields=['name', 'email', 'phone', 'street', 'city', 'country_id',
                'customer_rank', 'vat'],
        limit=limit,
        order='name asc',
    )
    return {"count": len(customers), "customers": customers}


def _get_products(client, name=None, limit=50):
    domain = [('sale_ok', '=', True), ('active', '=', True)]
    if name:
        domain.append(('name', 'ilike', name))

    products = client.search_read(
        'product.template',
        domain=domain,
        fields=['name', 'default_code', 'list_price', 'standard_price',
                'categ_id', 'uom_id', 'active'],
        limit=limit,
        order='name asc',
    )
    return {"count": len(products), "products": products}


def _get_purchase_orders(client, date_from=None, date_to=None, state=None, limit=50):
    domain = _build_date_domain('date_order', date_from, date_to)
    if state:
        domain.append(('state', '=', state))

    orders = client.search_read(
        'purchase.order',
        domain=domain,
        fields=['name', 'date_order', 'partner_id', 'amount_total',
                'state', 'currency_id', 'user_id'],
        limit=limit,
        order='date_order desc',
    )
    total = sum(o.get('amount_total', 0) for o in orders)
    return {"count": len(orders), "total_amount": total, "orders": orders}
