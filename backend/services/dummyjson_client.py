import requests

BASE = 'https://dummyjson.com'
TIMEOUT = 10


def get_products(limit=20):
    r = requests.get(f'{BASE}/products?limit={limit}&select=id,title,price,stock,category,brand,rating', timeout=TIMEOUT)
    return r.json().get('products', [])


def get_categories():
    r = requests.get(f'{BASE}/products/categories', timeout=TIMEOUT)
    return r.json()


def get_users(limit=10):
    r = requests.get(f'{BASE}/users?limit={limit}&select=id,firstName,lastName,email,company,address', timeout=TIMEOUT)
    return r.json().get('users', [])


def get_carts(limit=10):
    r = requests.get(f'{BASE}/carts?limit={limit}', timeout=TIMEOUT)
    return r.json().get('carts', [])


def build_context_summary():
    try:
        products = get_products(20)
        users = get_users(10)
        carts = get_carts(10)

        categories = {}
        for p in products:
            cat = p.get('category', 'other')
            categories.setdefault(cat, []).append(p)

        total_revenue = sum(c.get('total', 0) for c in carts)
        total_items = sum(c.get('totalQuantity', 0) for c in carts)
        avg_order = total_revenue / len(carts) if carts else 0
        low_stock = [p for p in products if p.get('stock', 999) < 20]

        lines = [
            'DATOS EN TIEMPO REAL — DummyJSON Store:',
            '',
            f'📦 INVENTARIO ({len(products)} productos):',
        ]
        for p in products[:8]:
            lines.append(f"  • {p['title']} — ${p['price']} USD | Stock: {p['stock']} | Rating: {p.get('rating', 'N/A')} | Categoría: {p['category']}")

        lines += ['', f'👥 CLIENTES ({len(users)} registrados):']
        for u in users[:5]:
            company = u.get('company', {})
            comp_name = company.get('name', 'N/A') if isinstance(company, dict) else str(company)
            lines.append(f"  • {u['firstName']} {u['lastName']} — {u['email']} | Empresa: {comp_name}")

        lines += ['', f'🛒 ÚLTIMAS ÓRDENES ({len(carts)} registros):']
        for c in carts[:5]:
            lines.append(f"  • Orden #{c['id']} — ${c.get('total', 0):.2f} USD | {c.get('totalProducts', 0)} productos | {c.get('totalQuantity', 0)} unidades")

        lines += [
            '',
            '📊 MÉTRICAS GENERALES:',
            f"  • Ingresos totales (muestra): ${total_revenue:.2f} USD",
            f"  • Ticket promedio: ${avg_order:.2f} USD",
            f"  • Unidades totales vendidas: {total_items}",
            f"  • Categorías activas: {', '.join(list(categories.keys())[:6])}",
        ]

        if low_stock:
            lines += ['', '⚠️ STOCK BAJO (menos de 20 unidades):']
            for p in low_stock[:5]:
                lines.append(f"  • {p['title']}: {p['stock']} unidades")

        return '\n'.join(lines)
    except Exception as e:
        return f'[Error al obtener datos de DummyJSON: {str(e)}]'
