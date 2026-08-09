"""Una empresa de ejemplo, para que Afable se pueda probar antes de cargar nada.

⭐ **El problema que resuelve.** Quien crea su cuenta abre el chat y recibe respuestas que
podría dar cualquier IA gratuita: la parte que vale —contestar con los datos de SU
empresa— solo aparece después de subir archivos y conectar sistemas. Eso son días, y la
mayoría no llega. Con datos de ejemplo, la primera pregunta ya se contesta con cifras y
con su fuente, que es la demostración que ningún texto de venta reemplaza.

**Son documentos de verdad, no un texto de contexto.** Se guardan como `CompanyDocument`,
se trocean y se indexan igual que los de un cliente, así que recorren exactamente el mismo
camino: la búsqueda semántica los encuentra, el agente los cita y el explorador los
muestra. Un "modo demo" que simulara respuestas no probaría nada — y se notaría el día que
alguien cargue lo suyo y funcione distinto.

⚠️ **Van marcados** (`source='ejemplo'`) y viven en su propio Workspace. Quien probó con
ellos tiene que poder sacarlos de una: si quedaran mezclados con los datos reales, el
agente citaría un contrato inventado como si fuera de la empresa, y esa es la peor forma
posible de perder la confianza de un cliente.
"""

WORKSPACE_EJEMPLO = 'Empresa de ejemplo'

# Una distribuidora chilena con lo que cualquiera reconoce: un contrato, la lista de
# precios, las reglas internas y el mes cerrado. Las cifras cuadran entre documentos a
# propósito — la gracia es poder preguntar algo que obligue a cruzar dos.
DOCUMENTOS = [
    {
        'titulo': 'Contrato de distribución — Comercial Andes',
        'texto': """CONTRATO DE DISTRIBUCIÓN

Entre Distribuidora Ejemplo SpA, RUT 76.543.210-9 (el Proveedor) y Comercial Andes
Limitada, RUT 77.111.222-3 (el Distribuidor).

PRIMERO — OBJETO. El Proveedor entrega al Distribuidor la venta exclusiva de la línea de
productos de limpieza industrial en la Región de Valparaíso.

SEGUNDO — PLAZO DE ENTREGA. El Proveedor despacha dentro de 5 días hábiles contados desde
la recepción de la orden de compra. Los despachos a regiones distintas de la Metropolitana
suman 2 días hábiles adicionales.

TERCERO — PRECIOS Y DESCUENTOS. El Distribuidor accede a la lista de precios mayorista con
un descuento del 18% sobre precio de lista. Sobre 500 unidades mensuales el descuento sube
a 22%.

CUARTO — PAGO. Las facturas se pagan a 30 días corridos desde su emisión. El atraso
superior a 15 días suspende los despachos hasta regularizar.

QUINTO — VIGENCIA. El contrato rige por 24 meses desde el 1 de marzo de 2026, renovable
automáticamente salvo aviso escrito con 60 días de anticipación.

SEXTO — MULTA POR INCUMPLIMIENTO. El atraso en la entrega superior a 10 días hábiles
faculta al Distribuidor a exigir una multa del 2% del valor de la orden por cada semana de
atraso, con tope del 10%.""",
    },
    {
        'titulo': 'Lista de precios mayorista 2026',
        'texto': """LISTA DE PRECIOS MAYORISTA — vigente desde el 1 de enero de 2026
Todos los valores en pesos chilenos, sin IVA.

LIMPIEZA INDUSTRIAL
  Desengrasante concentrado 5 L ......... $ 18.900   (código DG-5000)
  Detergente neutro 5 L ................. $ 12.400   (código DN-5000)
  Desinfectante amonio cuaternario 5 L .. $ 21.700   (código DA-5000)
  Cera para piso 5 L .................... $ 16.300   (código CP-5000)

PAPELERÍA E HIGIENE
  Papel higiénico institucional (bulto 12) $ 24.500  (código PH-12)
  Toalla de papel interfoliada (bulto 20)  $ 19.800  (código TP-20)
  Jabón espuma 800 ml (caja 6) .......... $ 27.300   (código JE-06)

DESCUENTOS POR VOLUMEN
  Desde 100 unidades mes .... 12%
  Desde 300 unidades mes .... 18%
  Desde 500 unidades mes .... 22%

Los precios se revisan cada 6 meses. Un alza mayor al 8% se avisa con 30 días.""",
    },
    {
        'titulo': 'Reglamento interno — resumen',
        'texto': """REGLAMENTO INTERNO DE ORDEN, HIGIENE Y SEGURIDAD (resumen)

JORNADA. La jornada ordinaria es de 40 horas semanales, de lunes a viernes de 08:30 a
17:30, con una hora de colación no imputable.

VACACIONES. 15 días hábiles por año trabajado. Se solicitan con 15 días de anticipación a
la jefatura directa y no se acumulan más de dos períodos.

TELETRABAJO. El personal administrativo puede trabajar hasta 2 días por semana desde su
domicilio, coordinados con su jefatura. Bodega y despacho son presenciales.

LICENCIAS. La licencia médica se presenta dentro de los 2 días hábiles siguientes a su
emisión.

SEGURIDAD EN BODEGA. Es obligatorio el uso de calzado de seguridad y guantes en el área de
carga. La manipulación de productos químicos exige antiparras y mascarilla.

GASTOS. Los gastos de representación se reembolsan con boleta o factura dentro del mes
siguiente. Sobre $200.000 requieren autorización previa de gerencia.""",
    },
    {
        'titulo': 'Cierre de ventas — julio 2026',
        'texto': """CIERRE DE VENTAS — JULIO 2026
Distribuidora Ejemplo SpA

RESUMEN
  Facturación neta ................ $ 84.320.000
  Mes anterior (junio) ............ $ 75.180.000
  Variación ....................... +12,2%
  Órdenes emitidas ................ 213
  Ticket promedio ................. $ 395.868

POR LÍNEA DE PRODUCTO
  Limpieza industrial ............. $ 51.400.000   (61%)
  Papelería e higiene ............. $ 24.900.000   (30%)
  Otros ........................... $  8.020.000    (9%)

TOP 5 CLIENTES
  1. Comercial Andes Ltda. ........ $ 11.240.000
  2. Supermercados del Sur ........ $  8.900.000
  3. Clínica Los Robles ........... $  6.470.000
  4. Hotelera Pacífico ............ $  5.180.000
  5. Casino Central ............... $  4.020.000

COBRANZA
  Por cobrar al cierre ............ $ 31.700.000
  Vencido a más de 30 días ........ $  6.240.000
  Cliente con mayor atraso ........ Hotelera Pacífico ($2.180.000, 47 días)

ALERTAS
  · Stock crítico en desengrasante DG-5000: quedan 78 unidades, venta mensual 340.
  · Comercial Andes superó las 500 unidades y pasó al descuento de 22%.""",
    },
    {
        'titulo': 'Política de despachos y devoluciones',
        'texto': """POLÍTICA DE DESPACHOS Y DEVOLUCIONES

DESPACHOS
  Región Metropolitana: 5 días hábiles desde la orden.
  Otras regiones: 7 días hábiles.
  Despacho sin costo sobre $500.000 netos. Bajo ese monto, $18.000 en RM y $29.000 en
  regiones.

RECEPCIÓN
  El cliente revisa al momento de la entrega. Las diferencias se anotan en la guía de
  despacho; sin esa anotación no se aceptan reclamos posteriores por faltantes.

DEVOLUCIONES
  Se aceptan dentro de 10 días corridos desde la recepción, con el producto sellado y su
  factura. Los productos químicos abiertos no se reciben de vuelta por normativa
  sanitaria.
  La devolución por error del Proveedor no tiene costo. Por decisión del cliente, se
  descuenta un 15% por gastos de reposición.

GARANTÍA
  Los productos tienen garantía por defecto de fabricación durante 6 meses. La garantía no
  cubre daño por almacenamiento inadecuado (humedad, exposición al sol o congelamiento).""",
    },
]

# Lo primero que conviene preguntarle. Son las tres que muestran de qué se trata: una
# obliga a cruzar dos documentos, otra a leer una cifra puntual, la tercera a razonar
# sobre una regla. Salen en la pantalla como botones para que nadie tenga que inventar
# la primera pregunta — que es donde la gente se traba.
PREGUNTAS_SUGERIDAS = [
    '¿Cuánto vendimos en julio y cómo nos fue contra junio?',
    'Según el contrato de Comercial Andes, ¿en cuántos días hay que despachar?',
    '¿Qué descuento le corresponde a un cliente que compra 600 unidades al mes?',
]


def crear_para(empresa, creado_por=None):
    """Deja los documentos de ejemplo en su propio Workspace, listos para preguntar.

    Es idempotente: si ya están, no los duplica. Devuelve `(workspace, cuántos creó)`.
    """
    from apps.workspaces.models import VISIBILITY_OPEN, Workspace

    from .models import CompanyDocument

    workspace, _ = Workspace.objects.get_or_create(
        organization=empresa, name=WORKSPACE_EJEMPLO,
        defaults={
            'visibility': VISIBILITY_OPEN,
            'icon': '🧪',
            'description': 'Una distribuidora inventada, para probar Afable sin cargar '
                           'nada. Se puede quitar de una sola vez.',
            'created_by': creado_por,
        },
    )

    creados = 0
    for datos in DOCUMENTOS:
        doc, nuevo = CompanyDocument.objects.get_or_create(
            organization=empresa, title=datos['titulo'], source='ejemplo',
            defaults={
                'file': f"ejemplo/{datos['titulo']}.txt",
                'content_type': 'text/plain',
                'extracted_text': datos['texto'],
                'editable': False,
                'uploaded_by': creado_por,
            },
        )
        workspace.documents.add(doc)
        if not nuevo:
            continue
        creados += 1
        # Se indexa igual que un documento real: si la búsqueda semántica no los
        # encontrara, el ejemplo funcionaría distinto que lo de verdad y no probaría nada.
        try:
            from services.indexing import indexar_documento
            indexar_documento(doc)
        except Exception:
            # Sin embeddings disponibles el agente igual los lee por el texto: el ejemplo
            # tiene que servir aunque falte el modelo de indexado.
            pass

    return workspace, creados


def quitar_de(empresa):
    """Saca los datos de ejemplo y su Workspace. Devuelve cuántos documentos borró."""
    from apps.workspaces.models import Workspace

    from .models import CompanyDocument

    # Se cuenta ANTES de borrar: `delete()` devuelve todo lo que cayó en cascada
    # (fragmentos indexados, relaciones con Workspaces), y ese número no es el que la
    # pantalla quiere mostrar — decir "se borraron 16" de 5 documentos asusta.
    del_ejemplo = CompanyDocument.objects.filter(organization=empresa, source='ejemplo')
    borrados = del_ejemplo.count()
    del_ejemplo.delete()
    Workspace.objects.filter(organization=empresa, name=WORKSPACE_EJEMPLO).delete()
    return borrados
