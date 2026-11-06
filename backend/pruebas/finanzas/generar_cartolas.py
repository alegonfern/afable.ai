"""Genera cartolas de PRUEBA a partir de los archivos de ejemplo del SII de esta carpeta.

Formato inventado pero habitual (Fecha;Descripción;Cargos;Abonos;Saldo). Sirven para probar la
conciliación mientras no hay cartolas reales. Correr desde esta carpeta:
    python generar_cartolas.py
"""

import csv
from datetime import datetime, timedelta


def leer(nombre):
    with open(nombre, encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter=';'))


def fecha(s):
    return datetime.strptime(s, '%d/%m/%Y')


ventas = [v for v in leer('rcv_ventas_ejemplo.csv') if v['Tipo Doc'] == '33']
compras = [c for c in leer('rcv_compras_ejemplo.csv') if c['Tipo Doc'] in ('33', '34') and '-' in c['RUT Proveedor'] and 'ABC' not in c['RUT Proveedor']]
honorarios = [h for h in leer('honorarios_recibidos_ejemplo.csv') if h['Estado'] == 'VIGENTE']

movs = []   # (fecha, descripción, monto con signo)
# Cobros: la mitad de las ventas de septiembre, una por una, 8 días después.
sep = [v for v in ventas if v['Fecha Docto'].split('/')[1] == '09']
for v in sep[::2]:
    movs.append((fecha(v['Fecha Docto']) + timedelta(days=8), f"TRANSF DE {v['Razon Social'].upper()}", int(v['Monto total'])))
# Un cliente paga dos facturas juntas.
por_cliente = {}
for v in sep[1::2]:
    por_cliente.setdefault(v['Rut cliente'], []).append(v)
dobles = next(vs for vs in por_cliente.values() if len(vs) >= 2)[:2]
movs.append((max(fecha(v['Fecha Docto']) for v in dobles) + timedelta(days=5),
             f"TRANSF DE {dobles[0]['Razon Social'].upper()}", sum(int(v['Monto total']) for v in dobles)))
# Pagos a proveedores de septiembre.
for c in [c for c in compras if c['Fecha Docto'].split('/')[1] == '09'][::2]:
    movs.append((fecha(c['Fecha Docto']) + timedelta(days=6), f"PAGO PROVEEDOR {c['Razon Social'].upper()}", -int(c['Monto Total'])))
# Honorarios: se paga el líquido.
for h in honorarios[:3]:
    movs.append((fecha(h['Fecha']) + timedelta(days=3), f"TRANSF A {h['Nombre o Razón Social'].upper()}", -int(h['Pagado'])))
# Sin documento: comisión, F29, retiro del dueño (por identificar).
movs += [
    (datetime(2026, 9, 30), 'COMISION MANTENCION CUENTA', -12990),
    (datetime(2026, 9, 18), 'PAGO F29 TESORERIA GENERAL', -1850000),
    (datetime(2026, 9, 25), 'TRANSFERENCIA A ALEXIS GONZALEZ', -1200000),
    # El traspaso: sale de la cuenta corriente y entra a la cuenta vista del BCI.
    (datetime(2026, 9, 26), 'TRASPASO A CUENTA VISTA', -2000000),
]
movs.sort(key=lambda m: m[0])

saldo = 15000000
with open('cartola_santander_ejemplo.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['Fecha', 'Descripción', 'Cargos', 'Abonos', 'Saldo'])
    for d, desc, monto in movs:
        saldo += monto
        w.writerow([d.strftime('%d/%m/%Y'), desc, -monto if monto < 0 else '', monto if monto > 0 else '', saldo])

with open('cartola_bci_ejemplo.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['Fecha', 'Descripción', 'Cargos', 'Abonos', 'Saldo'])
    w.writerow(['27/09/2026', 'TRASPASO DESDE CTA CTE', '', 2000000, 2350000])
    w.writerow(['29/09/2026', 'COMPRA POS SUPERMERCADO', 45670, '', 2304330])
print(len(movs), 'movimientos en la cartola del Santander')
