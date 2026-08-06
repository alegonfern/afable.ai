"""La primera hora: qué le falta a esta empresa para que Afable le sirva.

Alguien que se registra cae en una pantalla con un cuadro de texto y una galería de
agentes. Puede escribir, y el agente le contesta con lo que sabe cualquier modelo: nada de
su empresa. Los pasos que convierten eso en la herramienta que se le vendió —traer sus
archivos, conectar sus sistemas, invitar al equipo— están cada uno en su pantalla, y nada
los nombra en orden. Esto los nombra.

⭐ **El avance se CALCULA del estado real, no se guarda.** No hay una lista de tildes en la
base: cada paso es una consulta a lo que la empresa tiene. Guardar "listo" haría que el
panel siga felicitando a quien borró su única conexión, y ese es justo el momento en que
hay que avisarle. El precio es una consulta por paso; el beneficio es que el panel no puede
mentir.

**Sólo lo ve el administrador.** Los seis pasos son cosas que sólo él puede hacer: poner el
nombre de la empresa, conectar sistemas, invitar gente, contratar el plan. A un miembro
recién invitado, una lista de tareas que no puede completar es una lista de frustraciones.

Se guarda una sola cosa (`Workspace.onboarding_oculto`): que lo cerró a mano. Una empresa
que decidió no contratar plan nunca llegaría a 6 de 6, y un panel que no se puede cerrar
se vuelve un reproche permanente.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Membership
from .permissions import IsAdmin


def _nombre_es_el_automatico(workspace):
    """Si el nombre sigue siendo el que se le puso solo al registrarse.

    `create_for_owner` bautiza el Workspace "Workspace de Alexis". Mientras ese nombre
    siga ahí, la empresa no se ha presentado: el agente lo usa en el prompt y los
    comprobantes lo van a llevar impreso.
    """
    return workspace.name.startswith('Workspace de ')


def calcular_pasos(workspace):
    """Los seis pasos con su estado, en el orden en que conviene hacerlos.

    El orden no es arbitrario: primero lo que hace que las respuestas sirvan (quién es la
    empresa, qué sabe), después la primera pregunta —que es cuando se ve el valor—, y sólo
    entonces invitar al equipo y pagar. Pedir la tarjeta antes de que haya visto una
    respuesta útil es pedirle fe.
    """
    from apps.agents.models import Agent, Conversation
    from apps.organizations.models import CompanyDocument, SystemConnection
    from apps.payments.facturacion import suscripcion_vigente

    org = workspace.organization

    documentos = CompanyDocument.objects.filter(organization=org).count() if org else 0
    conexiones = SystemConnection.objects.filter(organization=org).count() if org else 0
    # Un agente PROPIO: los sembrados vienen sin `created_by`, y tener los de fábrica no
    # significa haber armado uno para la empresa.
    agentes_propios = (
        Agent.objects.filter(organization=org, created_by__isnull=False).count() if org else 0
    )
    personas = Membership.objects.filter(workspace=workspace).count()
    invitaciones = workspace.invitations.filter(accepted_at__isnull=True).count()
    # Una conversación CON RESPUESTA: haber escrito y que nadie contestara no es haber
    # probado nada. `autonoma` queda afuera porque esas las abre un Disparador por su
    # cuenta — que un agente publique solo no significa que la persona haya preguntado.
    conversaciones = (
        Conversation.objects
        .filter(agent__organization=org, autonoma=False, messages__role='assistant')
        .distinct().count()
        if org else 0
    )
    suscripcion = suscripcion_vigente(workspace)

    return [
        {
            'id': 'empresa',
            'titulo': 'Diga de qué se trata su empresa',
            'ayuda': 'El nombre, el rubro y en qué anda. Es lo que el agente lee antes de '
                     'contestar cualquier cosa.',
            'hecho': not _nombre_es_el_automatico(workspace) and bool(
                workspace.sector or workspace.description or workspace.logo
            ),
            'ruta': '/app/admin/workspace',
            'accion': 'Completar',
        },
        {
            'id': 'conocimiento',
            'titulo': 'Traiga lo que su empresa ya sabe',
            'ayuda': 'Suba sus documentos o conecte el sistema donde factura o lleva el '
                     'stock. Sin esto, el agente contesta como cualquier chat.',
            'hecho': documentos > 0 or conexiones > 0,
            'ruta': '/app/archivos',
            'accion': 'Subir o conectar',
            # "conexión" pierde la tilde en plural: pegarle "es" daba "conexiónes".
            'detalle': (
                f'{documentos} documento{"s" if documentos != 1 else ""} · '
                f'{conexiones} {"conexión" if conexiones == 1 else "conexiones"}'
            ),
        },
        {
            'id': 'pregunta',
            'titulo': 'Hágale la primera pregunta',
            'ayuda': 'Algo que hoy le tomaría rato averiguar a mano.',
            'hecho': conversaciones > 0,
            'ruta': '/app/chat',
            'accion': 'Preguntar',
        },
        {
            'id': 'agente',
            'titulo': 'Arme un agente para lo suyo',
            'ayuda': 'Uno con las instrucciones de su empresa, no el de fábrica: qué mirar, '
                     'qué nunca prometer, cómo contestar.',
            'hecho': agentes_propios > 0,
            'ruta': '/app/agentes/nuevo',
            'accion': 'Crear agente',
        },
        {
            'id': 'equipo',
            'titulo': 'Invite a su equipo',
            'ayuda': 'Afable es para el equipo: lo que uno conecta le sirve al resto.',
            'hecho': personas > 1 or invitaciones > 0,
            'ruta': '/app/admin/personas',
            'accion': 'Invitar',
        },
        {
            'id': 'plan',
            'titulo': 'Elija su plan',
            'ayuda': 'Cuando ya vio que le sirve. Los primeros días son de prueba.',
            'hecho': suscripcion is not None and suscripcion.vigente,
            'ruta': '/app/admin/facturacion',
            'accion': 'Ver planes',
        },
    ]


class PrimerosPasosView(APIView):
    """Qué le falta a esta empresa. Sólo para el administrador."""

    permission_classes = [IsAdmin]

    def get(self, request, slug):
        workspace = request.workspace
        pasos = calcular_pasos(workspace)
        hechos = sum(1 for p in pasos if p['hecho'])
        return Response({
            'pasos': pasos,
            'hechos': hechos,
            'total': len(pasos),
            # `terminado` es distinto de `oculto`: uno completó los pasos, el otro lo
            # cerró. La pantalla los trata igual (no dibuja nada), pero el dato sirve
            # para saber por qué.
            'terminado': hechos == len(pasos),
            'oculto': workspace.onboarding_oculto,
        })

    def post(self, request, slug):
        """Cerrarlo (o volver a abrirlo con `mostrar: true`)."""
        workspace = request.workspace
        workspace.onboarding_oculto = not request.data.get('mostrar', False)
        workspace.save(update_fields=['onboarding_oculto', 'updated_at'])
        return Response({'oculto': workspace.onboarding_oculto})
