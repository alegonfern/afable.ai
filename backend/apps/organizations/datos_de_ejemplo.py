"""Tres empresas de ejemplo, para que Afable se pueda probar antes de cargar nada.

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

## Por qué tres, y no una

Cada una está armada para que **haya algo que descubrir**, y para que ese algo se encuentre
de una manera distinta:

| Empresa | Lo que demuestra |
|---|---|
| **Distribuidora** | Comparar el mismo dato en dos momentos: un proveedor que subió precios sin avisar |
| **Constructora** | Fechas que se vencen: un subcontrato y un permiso que nadie está mirando |
| **Consultora** | Encontrar por significado: un trabajo ya hecho, con otras palabras, para otro cliente |

⭐ **La regla de estas demos: los hallazgos se cruzan entre dos documentos.** Que la IA lea
un PDF no impresiona a nadie en 2026. Que diga «este proveedor le subió 22% entre marzo y
agosto, y su contrato lo obligaba a avisar con 60 días» sí, porque eso nadie lo tenía a la
vista.

⚠️ **Van marcados** (`source='ejemplo'`) y viven en su propio Workspace. Quien probó con
ellos tiene que poder sacarlos de una: si quedaran mezclados con los datos reales, el
agente citaría un contrato inventado como si fuera de la empresa, y esa es la peor forma
posible de perder la confianza de un cliente.

Todos los nombres, RUT y cifras son inventados.
"""

WORKSPACE_EJEMPLO = 'Empresa de ejemplo'

DISTRIBUIDORA = 'distribuidora'
CONSTRUCTORA = 'constructora'
CONSULTORA = 'consultora'


# ── Distribuidora ─────────────────────────────────────────────────────────────
# El caso más universal. Muestra comparar el mismo dato en dos momentos.

DOCS_DISTRIBUIDORA = [
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

TERCERO — PRECIOS. Los precios se mantienen fijos durante el trimestre. Toda modificación
debe comunicarse por escrito con al menos 60 días corridos de anticipación.

CUARTO — DESCUENTOS POR VOLUMEN. Sobre 500 unidades mensuales corresponde un 8% de
descuento. Sobre 1.000 unidades, 12%.

QUINTO — VIGENCIA. Doce meses renovables, contados desde el 1 de enero de 2026.""",
    },
    {
        'titulo': 'Lista de precios proveedor Quimex — marzo 2026',
        'texto': """LISTA DE PRECIOS — QUIMEX INSUMOS SpA
Vigencia: marzo 2026

Detergente industrial 5L .............. $4.500 por unidad
Desengrasante concentrado 5L .......... $6.200 por unidad
Cloro industrial 10L .................. $3.800 por unidad
Jabón espuma 5L ....................... $5.100 por unidad
Paños microfibra (pack 12) ............ $2.400 por pack

Condiciones: pago a 30 días. Despacho sin costo sobre $500.000.
Estos precios rigen para el trimestre en curso.""",
    },
    {
        'titulo': 'Lista de precios proveedor Quimex — agosto 2026',
        'texto': """LISTA DE PRECIOS — QUIMEX INSUMOS SpA
Vigencia: agosto 2026

Detergente industrial 5L .............. $5.490 por unidad
Desengrasante concentrado 5L .......... $7.564 por unidad
Cloro industrial 10L .................. $4.636 por unidad
Jabón espuma 5L ....................... $6.222 por unidad
Paños microfibra (pack 12) ............ $2.928 por pack

Condiciones: pago a 30 días. Despacho sin costo sobre $500.000.
Ajuste general aplicado a la lista anterior por variación de costos de importación.""",
    },
    {
        'titulo': 'Ventas por cliente — enero a agosto 2026',
        'texto': """RESUMEN DE VENTAS POR CLIENTE (montos en pesos)

Cliente                    Ene      Mar      May      Jul      Ago
Comercial Andes         8.400.000  8.900.000  9.100.000  9.400.000  9.600.000
Supermercados Lolen     5.200.000  5.100.000  5.300.000  5.250.000  5.400.000
Aseo Integral Maipú     3.100.000  3.050.000  3.200.000  3.150.000  3.300.000
Servicios Bío Bío       2.800.000  2.900.000        0          0          0
Limpieza Austral        1.900.000  2.000.000  1.950.000  2.100.000  2.050.000

Total mensual          21.400.000 21.950.000 19.550.000 19.900.000 20.350.000

Nota: el total de agosto sube 2,3% contra julio.""",
    },
    {
        'titulo': 'Inventario al cierre de agosto 2026',
        'texto': """INVENTARIO — CIERRE AGOSTO 2026

Producto                        Stock    Salidas último trimestre
Detergente industrial 5L          420            1.180
Desengrasante concentrado 5L      310              940
Cloro industrial 10L              280              760
Jabón espuma 5L                   190              520
Paños microfibra (pack 12)        640               35
Escobillón industrial             410               12

Los dos últimos ítems concentran el 38% del valor inmovilizado.""",
    },
    {
        'titulo': 'Reglas internas de despacho y cobranza',
        'texto': """REGLAS INTERNAS — OPERACIÓN

DESPACHO
- Toda orden entra al sistema el mismo día que se recibe.
- Los despachos a regiones salen los martes y jueves.
- Una orden sobre $2.000.000 requiere visto bueno de administración.

COBRANZA
- Las facturas se emiten el día del despacho, nunca después.
- A los 15 días de vencida se envía el primer recordatorio.
- A los 45 días se suspende el despacho al cliente hasta regularizar.

PROVEEDORES
- Toda alza de precios debe quedar registrada y comparada con la lista anterior.
- Si el proveedor no avisó con la anticipación pactada, se reclama por escrito.""",
    },
]

PREGUNTAS_DISTRIBUIDORA = [
    '¿Algún proveedor nos subió los precios este año? ¿Cuánto?',
    '¿Hay algún cliente que haya dejado de comprarnos?',
    '¿Qué productos tenemos en stock que casi no salen?',
]


# ── Constructora ──────────────────────────────────────────────────────────────
# Muy de la región y muy documental. Muestra fechas que se vencen.

DOCS_CONSTRUCTORA = [
    {
        'titulo': 'Contrato de obra — Edificio Los Robles',
        'texto': """CONTRATO DE EJECUCIÓN DE OBRA

Mandante: Inmobiliaria Los Robles SpA, RUT 76.888.111-2
Contratista: Constructora Ejemplo Limitada, RUT 77.222.333-4

OBJETO. Construcción de edificio habitacional de 6 pisos, 24 departamentos, en calle Los
Robles 1450, comuna de Ñuñoa.

MONTO. UF 48.500, a suma alzada.

PLAZO. 14 meses corridos desde el acta de entrega de terreno, firmada el 3 de febrero de
2026. Fecha de término prevista: 3 de abril de 2027.

ESTADOS DE PAGO. Mensuales, contra avance certificado por la inspección técnica. El
mandante paga dentro de 30 días de aprobado el estado de pago.

MULTAS. UF 25 por cada día corrido de atraso en la entrega final.

RETENCIONES. Se retiene el 5% de cada estado de pago, devuelto a la recepción municipal
definitiva.""",
    },
    {
        'titulo': 'Subcontrato instalaciones eléctricas — Eléctrica Sur',
        'texto': """SUBCONTRATO DE INSTALACIONES ELÉCTRICAS

Contratista: Constructora Ejemplo Limitada
Subcontratista: Eléctrica Sur SpA, RUT 78.444.555-6

ALCANCE. Instalación eléctrica completa del Edificio Los Robles: canalizaciones, tableros,
enchufes, iluminación de espacios comunes y empalme definitivo.

MONTO. UF 4.200.

VIGENCIA. Desde el 15 de marzo de 2026 hasta el 22 de septiembre de 2026.

RENOVACIÓN. El presente subcontrato no se renueva de forma automática. Para continuar los
trabajos después de la fecha de término, las partes deben suscribir un anexo con al menos
15 días corridos de anticipación al vencimiento.

GARANTÍA. Boleta de garantía por UF 420, vigente hasta 90 días después del término.""",
    },
    {
        'titulo': 'Permiso de edificación — Dirección de Obras Ñuñoa',
        'texto': """PERMISO DE EDIFICACIÓN N° 214/2026
Dirección de Obras Municipales — Ilustre Municipalidad de Ñuñoa

Propietario: Inmobiliaria Los Robles SpA
Obra: Edificio habitacional, 6 pisos, 24 unidades
Dirección: Los Robles 1450

Fecha de otorgamiento: 20 de enero de 2026.
Vigencia: el permiso caduca si las obras no se inician dentro de 12 meses, y si se
paralizan por más de 6 meses continuos.

OBSERVACIÓN. La aprobación del proyecto de alcantarillado particular se otorgó de forma
provisoria y debe regularizarse ante la sanitaria antes del 30 de septiembre de 2026. De lo
contrario, la recepción final quedará observada.""",
    },
    {
        'titulo': 'Estados de pago cursados — Edificio Los Robles',
        'texto': """ESTADOS DE PAGO — EDIFICIO LOS ROBLES

N°   Período      Avance   Monto UF   Aprobado ITO   Facturado
1    Feb 2026      6%        2.910     Sí             Sí
2    Mar 2026     13%        3.395     Sí             Sí
3    Abr 2026     21%        3.880     Sí             Sí
4    May 2026     29%        3.880     Sí             Sí
5    Jun 2026     38%        4.365     Sí             Sí
6    Jul 2026     46%        3.880     Sí             Sí
7    Ago 2026     54%        3.880     Sí             No

Avance acumulado a agosto: 54%. Monto cursado acumulado: UF 26.190.
El estado de pago 7 fue aprobado por la inspección técnica el 4 de septiembre.""",
    },
    {
        'titulo': 'Libro de obra — resumen agosto 2026',
        'texto': """LIBRO DE OBRA — ANOTACIONES DE AGOSTO 2026

05-08. Se recibe hormigón para losa piso 5. Ensayo de probetas conforme.
09-08. Lluvia. Se suspenden faenas de fachada durante dos días.
14-08. La inspección técnica observa la altura de dos ductos en piso 3. Se corrige.
19-08. Ingresa Eléctrica Sur a canalizaciones de pisos 4 y 5.
23-08. Se solicita a la sanitaria la factibilidad definitiva de alcantarillado. Sin
       respuesta a la fecha.
28-08. Avance de obra certificado: 54%.

PENDIENTES ANOTADOS
- Regularización de alcantarillado ante la sanitaria.
- Definir continuidad de Eléctrica Sur para los pisos 6 y espacios comunes.""",
    },
    {
        'titulo': 'Presupuesto y control de costos — agosto 2026',
        'texto': """CONTROL DE COSTOS — EDIFICIO LOS ROBLES (UF)

Partida                 Presupuesto   Gastado a la fecha   Desviación
Obra gruesa                18.400          17.950              -450
Instalaciones              9.800            5.100                 —
Terminaciones             11.200            2.300                 —
Gastos generales           4.600            2.980              +180
Imprevistos                2.000              620                 —
Utilidad esperada          2.500                —                 —

Total contrato             48.500

La partida de gastos generales viene sobre presupuesto desde junio, principalmente por
arriendo de andamios prolongado.""",
    },
]

PREGUNTAS_CONSTRUCTORA = [
    '¿Tenemos algún contrato o permiso por vencer en las próximas semanas?',
    '¿Hay algún estado de pago aprobado que todavía no hayamos facturado?',
    '¿Cómo viene la obra contra el presupuesto?',
]


# ── Consultora ────────────────────────────────────────────────────────────────
# El caso del conocimiento disperso. Muestra encontrar por significado.

DOCS_CONSULTORA = [
    {
        'titulo': 'Propuesta — Rediseño de procesos de bodega para Alimentos del Valle',
        'texto': """PROPUESTA DE SERVICIOS
Cliente: Alimentos del Valle SpA
Fecha: abril de 2026

SITUACIÓN. La bodega de producto terminado no tiene ubicaciones definidas. El personal
busca por memoria, los inventarios cíclicos arrojan diferencias de hasta 7% y los despachos
salen con atraso en temporada alta.

ALCANCE PROPUESTO
1. Levantamiento de la operación actual de bodega (2 semanas).
2. Diseño de layout con ubicaciones codificadas y criterio de rotación.
3. Definición de procedimientos de recepción, picking y despacho.
4. Capacitación al equipo y acompañamiento durante un ciclo completo.

PLAZO. 10 semanas.
HONORARIOS. UF 620, en tres cuotas contra hitos.

RESULTADO ESPERADO. Reducir la diferencia de inventario bajo 2% y eliminar los atrasos de
despacho atribuibles a búsqueda de producto.""",
    },
    {
        'titulo': 'Informe final — Ordenamiento de centro de distribución, Frutícola Maitén',
        'texto': """INFORME FINAL DE PROYECTO
Cliente: Frutícola Maitén Limitada
Cierre: noviembre de 2025

TRABAJO REALIZADO. Reordenamiento completo del centro de distribución: se definieron
ubicaciones codificadas por pasillo y altura, se estableció criterio de rotación por
frecuencia de salida, y se rescribieron los procedimientos de recepción y despacho.

METODOLOGÍA APLICADA
- Cuatro semanas de levantamiento en terreno con acompañamiento a turnos.
- Clasificación de referencias por frecuencia de movimiento.
- Rediseño de layout y señalética.
- Capacitación en dos jornadas y seguimiento durante seis semanas.

RESULTADOS MEDIDOS
- Diferencia de inventario: bajó de 6,4% a 1,8%.
- Tiempo promedio de picking: bajó de 11 a 4 minutos por pedido.
- Despachos fuera de plazo: de 14% a 3%.

ENTREGABLES. Manual de procedimientos, planos de layout, matriz de ubicaciones y material
de capacitación. Todo el material quedó en formato editable.""",
    },
    {
        'titulo': 'Contrato marco de servicios — Alimentos del Valle',
        'texto': """CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS

Entre Consultora Ejemplo SpA, RUT 76.999.888-1, y Alimentos del Valle SpA.

PRIMERO. La Consultora prestará servicios de asesoría en gestión de operaciones, según las
propuestas específicas que las partes acuerden.

SEGUNDO — CONFIDENCIALIDAD. La Consultora se obliga a mantener reserva sobre la información
del Cliente por un plazo de tres años desde el término de cada proyecto.

TERCERO — PROPIEDAD DE LOS ENTREGABLES. Los informes y manuales elaborados son de propiedad
del Cliente. La Consultora conserva el derecho de reutilizar la metodología, los marcos de
trabajo y el conocimiento general aplicado, sin revelar información del Cliente.

CUARTO — NO COMPETENCIA. Durante la vigencia del contrato y por seis meses posteriores, la
Consultora no prestará servicios de la misma naturaleza a empresas de alimentos procesados
de la Región del Maule.

QUINTO — FACTURACIÓN. Contra hitos aprobados, pago a 30 días.""",
    },
    {
        'titulo': 'Registro de horas — abril a agosto 2026',
        'texto': """REGISTRO DE HORAS POR PROYECTO

Proyecto                          Horas   Facturadas   Pendientes
Alimentos del Valle — bodega        412        412            0
Maderas Coihue — costos             186        186            0
Alimentos del Valle — adicionales    64          0           64
Transportes Quilín — diagnóstico     98         98            0
Interno — desarrollo de propuestas  120          —            —

Las 64 horas de adicionales corresponden a trabajo solicitado fuera del alcance original,
autorizado por correo en junio y julio. Valor hora del contrato: UF 1,4.""",
    },
    {
        'titulo': 'Acta de reunión — Alimentos del Valle, 12 de agosto',
        'texto': """ACTA DE REUNIÓN
Cliente: Alimentos del Valle SpA
Fecha: 12 de agosto de 2026
Asistentes: gerente de operaciones del cliente, jefe de bodega, equipo consultor.

TEMAS TRATADOS
1. Avance del rediseño de bodega: layout aprobado, señalética en instalación.
2. El cliente solicita extender el trabajo al centro de distribución de Talca, con la misma
   metodología.
3. Se discute el tratamiento de las horas adicionales trabajadas en junio y julio.

ACUERDOS
- El equipo prepara una propuesta para Talca antes de fin de mes.
- Las horas adicionales se regularizan en la próxima facturación.
- El jefe de bodega enviará las cifras de inventario cíclico de julio.

PENDIENTE. La propuesta de Talca no se ha enviado a la fecha de esta acta.""",
    },
    {
        'titulo': 'Metodología interna — proyectos de operaciones',
        'texto': """METODOLOGÍA INTERNA — PROYECTOS DE OPERACIONES

ETAPA 1 — LEVANTAMIENTO
Acompañamiento en terreno, no entrevistas de escritorio. Mínimo dos turnos completos.
Se documenta lo que se hace, no lo que se dice que se hace.

ETAPA 2 — DIAGNÓSTICO
Clasificación por frecuencia de movimiento. Medición de tiempos reales.
Toda afirmación del diagnóstico tiene que tener un dato detrás.

ETAPA 3 — DISEÑO
Layout, procedimientos y responsables. Se diseña con el equipo que va a operar, no para él.

ETAPA 4 — IMPLEMENTACIÓN Y ACOMPAÑAMIENTO
Capacitación y seguimiento por al menos un ciclo completo de operación.

REUTILIZACIÓN. Los marcos y plantillas de proyectos anteriores se reutilizan siempre que el
contrato lo permita. Antes de partir de cero, revisar qué se hizo en proyectos parecidos.""",
    },
]

PREGUNTAS_CONSULTORA = [
    '¿Ya hicimos algún trabajo parecido al que nos están pidiendo en bodega?',
    '¿Tenemos horas trabajadas que todavía no hemos facturado?',
    '¿Qué nos limita el contrato con Alimentos del Valle?',
]


EMPRESAS = {
    DISTRIBUIDORA: {
        'nombre': 'Distribuidora de ejemplo',
        'para_quien': 'Comercio y distribución',
        'muestra': 'Comparar el mismo dato en dos momentos.',
        'documentos': DOCS_DISTRIBUIDORA,
        'preguntas': PREGUNTAS_DISTRIBUIDORA,
    },
    CONSTRUCTORA: {
        'nombre': 'Constructora de ejemplo',
        'para_quien': 'Construcción y obras',
        'muestra': 'Fechas que se vencen y nadie está mirando.',
        'documentos': DOCS_CONSTRUCTORA,
        'preguntas': PREGUNTAS_CONSTRUCTORA,
    },
    CONSULTORA: {
        'nombre': 'Consultora de ejemplo',
        'para_quien': 'Servicios profesionales',
        'muestra': 'Encontrar por significado lo que ya se hizo.',
        'documentos': DOCS_CONSULTORA,
        'preguntas': PREGUNTAS_CONSULTORA,
    },
}

# Compatibilidad: quien ya importaba estos nombres sigue recibiendo la distribuidora, que
# es la que estaba antes de que fueran tres.
DOCUMENTOS = DOCS_DISTRIBUIDORA
PREGUNTAS_SUGERIDAS = PREGUNTAS_DISTRIBUIDORA


def catalogo():
    """Las tres empresas, para que la pantalla las ofrezca."""
    return [
        {'clave': clave, 'nombre': datos['nombre'], 'para_quien': datos['para_quien'],
         'muestra': datos['muestra'], 'documentos': len(datos['documentos']),
         'preguntas': datos['preguntas']}
        for clave, datos in EMPRESAS.items()
    ]


def preguntas_de(tipo):
    return EMPRESAS.get(tipo, EMPRESAS[DISTRIBUIDORA])['preguntas']


def crear_para(empresa, creado_por=None, tipo=DISTRIBUIDORA):
    """Deja los documentos de ejemplo en su propio Workspace, listos para preguntar.

    Es idempotente: si ya están, no los duplica. Devuelve `(workspace, cuántos creó)`.

    `tipo` elige cuál de las tres empresas se carga. El default es la distribuidora, que es
    la que existía cuando esto era una sola — así nadie que ya llamaba a esta función
    empieza a recibir otra cosa.
    """
    from apps.archivos.models import Carpeta
    from apps.workspaces.models import VISIBILITY_OPEN, Workspace

    from .models import CompanyDocument

    datos_empresa = EMPRESAS.get(tipo, EMPRESAS[DISTRIBUIDORA])

    workspace, _ = Workspace.objects.get_or_create(
        organization=empresa, name=WORKSPACE_EJEMPLO,
        defaults={
            'visibility': VISIBILITY_OPEN,
            'icon': '🧪',
            'description': f"{datos_empresa['nombre']}, para probar Afable sin cargar "
                           'nada. Se puede quitar de una sola vez.',
            'created_by': creado_por,
        },
    )

    # Los documentos del ejemplo viven en una carpeta, igual que los de verdad: es de
    # donde un agente saca su alcance desde el 2026-08-31. Si el ejemplo los dejara
    # sueltos, probaría un camino que ya no existe.
    carpeta, _ = Carpeta.objects.get_or_create(
        organization=empresa, parent=None, name=WORKSPACE_EJEMPLO,
        defaults={'created_by': creado_por},
    )

    creados = 0
    for datos in datos_empresa['documentos']:
        doc, nuevo = CompanyDocument.objects.get_or_create(
            organization=empresa, title=datos['titulo'], source='ejemplo',
            defaults={
                'file': f"ejemplo/{datos['titulo']}.txt",
                'content_type': 'text/plain',
                'extracted_text': datos['texto'],
                'editable': False,
                'uploaded_by': creado_por,
                'carpeta': carpeta,
            },
        )
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
