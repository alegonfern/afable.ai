"""
Crea y puebla una base PostgreSQL "fuente" demo (clientes, productos, stock,
pedidos) que simula el sistema externo de una empresa. Afable se conecta a ella
como conector PostgreSQL para el PMV (chat con datos en vivo).

Uso:  python manage.py seed_source_db
"""
import random
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

DEMO_DB = 'afable_source_demo'

NOMBRES = ['Comercial Andes', 'Distribuidora Pacífico', 'Muebles del Sur', 'Importadora Lota',
           'Retail Aconcagua', 'Hogar y Diseño', 'Oficinas Plus', 'Casa Bordemar',
           'Ferretería Maipo', 'Almacenes Quillota', 'Grupo Curicó', 'Bazar Ñuñoa']
SUFIJOS = ['SpA', 'Ltda', 'S.A.', 'EIRL']
CIUDADES = ['Santiago', 'Valparaíso', 'Concepción', 'La Serena', 'Temuco', 'Antofagasta']
CATEGORIAS = {
    'Sillas': (39990, 129990), 'Mesas': (89990, 349990), 'Escritorios': (69990, 299990),
    'Estanterías': (29990, 159990), 'Lámparas': (12990, 79990),
}
ESTADOS = ['pagado', 'pagado', 'por_despachar', 'despachado', 'despachado', 'anulado']


def _rut():
    return f"{random.randint(6, 25)}.{random.randint(100, 999)}.{random.randint(100, 999)}-{random.choice('0123456789K')}"


class Command(BaseCommand):
    help = 'Crea/puebla la base Postgres fuente demo (afable_source_demo) para conectar Afable como sistema externo.'

    def handle(self, *args, **options):
        random.seed(42)
        import psycopg

        db = settings.DATABASES['default']
        host = db.get('HOST') or 'localhost'
        port = db.get('PORT') or 5432
        user, password = db['USER'], db['PASSWORD']

        # 1) Crear la BD si no existe (CREATE DATABASE requiere autocommit)
        admin = psycopg.connect(host=host, port=port, user=user, password=password,
                                dbname=db['NAME'], autocommit=True)
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DEMO_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE {DEMO_DB}')
                self.stdout.write(self.style.SUCCESS(f'Base {DEMO_DB} creada.'))
            else:
                self.stdout.write(f'Base {DEMO_DB} ya existe; recreando tablas.')
        admin.close()

        # 2) Tablas + datos
        conn = psycopg.connect(host=host, port=port, user=user, password=password,
                               dbname=DEMO_DB, autocommit=True)
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS pedido_lineas, pedidos, stock, productos, clientes CASCADE')
            cur.execute("""
                CREATE TABLE clientes (
                    id SERIAL PRIMARY KEY, nombre TEXT, rut TEXT, email TEXT,
                    ciudad TEXT, saldo NUMERIC(12,0) DEFAULT 0, creado DATE)""")
            cur.execute("""
                CREATE TABLE productos (
                    id SERIAL PRIMARY KEY, sku TEXT, nombre TEXT, categoria TEXT, precio NUMERIC(12,0))""")
            cur.execute("""
                CREATE TABLE stock (
                    id SERIAL PRIMARY KEY, producto_id INT REFERENCES productos(id),
                    bodega TEXT, disponible INT)""")
            cur.execute("""
                CREATE TABLE pedidos (
                    id SERIAL PRIMARY KEY, numero TEXT, cliente_id INT REFERENCES clientes(id),
                    fecha DATE, estado TEXT, total NUMERIC(12,0) DEFAULT 0)""")
            cur.execute("""
                CREATE TABLE pedido_lineas (
                    id SERIAL PRIMARY KEY, pedido_id INT REFERENCES pedidos(id),
                    producto_id INT REFERENCES productos(id), cantidad INT, precio_unit NUMERIC(12,0))""")

            # Clientes
            clientes = []
            for _ in range(50):
                nombre = f"{random.choice(NOMBRES)} {random.choice(SUFIJOS)}"
                clientes.append((nombre, _rut(), f"contacto{random.randint(1,999)}@empresa.cl",
                                 random.choice(CIUDADES), random.choice([0, 0, 0, random.randint(50, 800) * 1000]),
                                 date.today() - timedelta(days=random.randint(30, 900))))
            cur.executemany(
                "INSERT INTO clientes (nombre, rut, email, ciudad, saldo, creado) VALUES (%s,%s,%s,%s,%s,%s)",
                clientes)

            # Productos
            productos = []
            for cat, (lo, hi) in CATEGORIAS.items():
                for i in range(8):
                    precio = round(random.randint(lo, hi), -2)
                    productos.append((f"{cat[:3].upper()}-{random.randint(1000,9999)}",
                                      f"{cat[:-1]} modelo {random.choice(['Eames','Nordic','Loft','Roble','Urban','Cima'])} {i+1}",
                                      cat, precio))
            cur.executemany(
                "INSERT INTO productos (sku, nombre, categoria, precio) VALUES (%s,%s,%s,%s)", productos)
            cur.execute("SELECT id, precio FROM productos")
            prod_rows = cur.fetchall()
            prod_ids = [r[0] for r in prod_rows]
            precio_by_id = {r[0]: int(r[1]) for r in prod_rows}

            # Stock (algunos en quiebre)
            stock = []
            for pid in prod_ids:
                stock.append((pid, 'Bodega Santiago', random.choice([0, 0, 3, 8, 14, 25, 40, 60])))
                if random.random() < 0.4:
                    stock.append((pid, 'Bodega Valparaíso', random.randint(0, 30)))
            cur.executemany(
                "INSERT INTO stock (producto_id, bodega, disponible) VALUES (%s,%s,%s)", stock)

            cur.execute("SELECT id FROM clientes")
            cli_ids = [r[0] for r in cur.fetchall()]

            # Pedidos + líneas (últimos 60 días, incluye mes actual)
            for n in range(300):
                cli = random.choice(cli_ids)
                fecha = date.today() - timedelta(days=random.randint(0, 60))
                estado = random.choice(ESTADOS)
                cur.execute(
                    "INSERT INTO pedidos (numero, cliente_id, fecha, estado, total) VALUES (%s,%s,%s,%s,0) RETURNING id",
                    (f"P-{10000+n}", cli, fecha, estado))
                ped_id = cur.fetchone()[0]
                total = 0
                for _ in range(random.randint(1, 4)):
                    pid = random.choice(prod_ids)
                    qty = random.randint(1, 6)
                    pu = precio_by_id[pid]
                    total += qty * pu
                    cur.execute(
                        "INSERT INTO pedido_lineas (pedido_id, producto_id, cantidad, precio_unit) VALUES (%s,%s,%s,%s)",
                        (ped_id, pid, qty, pu))
                if estado != 'anulado':
                    cur.execute("UPDATE pedidos SET total = %s WHERE id = %s", (total, ped_id))
        conn.close()

        self.stdout.write(self.style.SUCCESS('\n✓ Base fuente demo poblada: 50 clientes, 40 productos, stock, 300 pedidos.\n'))
        self.stdout.write('Conecta Afable en Integraciones → PostgreSQL con estos datos:')
        self.stdout.write(f'  Host:       {host}')
        self.stdout.write(f'  Puerto:     {port}')
        self.stdout.write(f'  Base:       {DEMO_DB}')
        self.stdout.write(f'  Usuario:    {user}')
        self.stdout.write(f'  Contraseña: {password}')
        self.stdout.write('\nLuego prueba en el chat: "¿cuánto vendimos este mes?" o "¿qué productos están en quiebre de stock?"')
