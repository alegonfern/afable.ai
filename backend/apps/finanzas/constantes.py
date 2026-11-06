"""Constantes tributarias de Chile para el módulo de Finanzas.

Cada valor vive donde de verdad cambia (decidido con Alexis el 17-10-2026):
- El IVA es igual para todos: constante.
- La retención de honorarios cambia por AÑO, por ley: tabla por año.
- El régimen y la tasa de PPM son de cada empresa: van en `ConfiguracionTributaria`, no acá.
  Acá solo queda la tasa SUGERIDA por régimen, que la empresa confirma con su último F29.

Todo lo que sale de estos números se muestra como provisión estimada, no como declaración.
"""

from decimal import Decimal

IVA = Decimal('0.19')

# Ley 21.133: la retención de las boletas de honorarios sube cada año hasta 17% en 2028.
# Al cambiar la ley, se agrega o corrige una línea. Fuera de la tabla se usa el año más cercano.
RETENCION_HONORARIOS = {
    2024: Decimal('13.75'),
    2025: Decimal('14.50'),
    2026: Decimal('15.25'),
    2027: Decimal('16.00'),
    2028: Decimal('17.00'),
}


def retencion_honorarios(anio: int) -> Decimal:
    """Porcentaje de retención vigente en `anio` (13.75 = 13,75%)."""
    if anio in RETENCION_HONORARIOS:
        return RETENCION_HONORARIOS[anio]
    cercano = min(RETENCION_HONORARIOS, key=lambda a: abs(a - anio))
    return RETENCION_HONORARIOS[cercano]


REGIMEN_PRO_PYME_GENERAL = '14D3'
REGIMEN_PRO_PYME_TRANSPARENTE = '14D8'
REGIMEN_GENERAL = '14A'

REGIMENES = [
    (REGIMEN_PRO_PYME_GENERAL, 'Pro Pyme General (14 D N°3)'),
    (REGIMEN_PRO_PYME_TRANSPARENTE, 'Pro Pyme Transparente (14 D N°8)'),
    (REGIMEN_GENERAL, 'Régimen General semi integrado (14 A)'),
]

# Tasa de PPM SUGERIDA al elegir el régimen (porcentaje sobre los ingresos del mes). Es solo
# un punto de partida: la tasa real es la de cada empresa y está en su último F29. Por eso la
# configuración la deja editable y la pantalla pide confirmarla. ⚠️ Confirmar con un contador.
PPM_SUGERIDA = {
    REGIMEN_PRO_PYME_GENERAL: Decimal('0.25'),
    REGIMEN_PRO_PYME_TRANSPARENTE: Decimal('0.20'),
    REGIMEN_GENERAL: Decimal('1.00'),
}

# Libros del SII que se pueden cargar.
LIBRO_COMPRAS = 'compras'
LIBRO_VENTAS = 'ventas'
LIBRO_HONORARIOS = 'honorarios'
LIBROS = [
    (LIBRO_COMPRAS, 'Compras'),
    (LIBRO_VENTAS, 'Ventas'),
    (LIBRO_HONORARIOS, 'Boletas de honorarios recibidas'),
]

# Tipos de documento del SII que aparecen en el Registro de Compras y Ventas.
TIPOS_DTE = {
    '30': 'Factura',
    '32': 'Factura no afecta o exenta',
    '33': 'Factura electrónica',
    '34': 'Factura no afecta o exenta electrónica',
    '39': 'Boleta electrónica',
    '41': 'Boleta exenta electrónica',
    '46': 'Factura de compra electrónica',
    '48': 'Comprobante de pago electrónico',
    '52': 'Guía de despacho electrónica',
    '56': 'Nota de débito electrónica',
    '61': 'Nota de crédito electrónica',
    'BHE': 'Boleta de honorarios electrónica',
}
# Las notas de crédito restan: al sumar se multiplican por -1.
TIPOS_QUE_RESTAN = {'61'}

# Categorías con las que parte cada empresa. Se pueden editar y agregar otras.
CATEGORIAS_INICIALES = {
    'ingreso': ['Venta de productos', 'Venta de servicios', 'Otros ingresos'],
    'gasto': [
        'Costo de mercadería', 'Insumos y materiales', 'Arriendo', 'Remuneraciones',
        'Honorarios', 'Servicios básicos', 'Software y suscripciones', 'Marketing',
        'Transporte y logística', 'Mantención y reparaciones', 'Asesorías',
        'Gastos bancarios y comisiones', 'Otros gastos',
    ],
}

# Días que se suponen entre el documento y su pago mientras Afable no conoce el plazo real de
# esa contraparte. Con eso se calcula el vencimiento y qué se da por pagado al importar.
PLAZO_PAGO_POR_DEFECTO = 30

MEDIOS_DE_PAGO = ['Transferencia', 'Tarjeta de crédito', 'Tarjeta de débito', 'Efectivo',
                  'Cheque', 'Crédito del proveedor', 'Otro']
