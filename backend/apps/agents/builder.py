"""Constructor de agentes: crear y editar un agente desde la app, sin codigo.

Es la promesa central del producto ("creas tantos agentes como necesites, desde
cero") y era lo unico de esa promesa que no se podia hacer: el boton
"Crear > Agente nuevo" de la galeria navegaba a la galeria misma.

Por que un endpoint nuevo y no el `POST /agents/` que ya existia: ese resuelve el
permiso con `Organization.objects.filter(owner=request.user)`, o sea que solo el
dueño crea y la politica del Workspace (`agent_creation_policy`) no se consulta
nunca. Peor, toma la organizacion DEL CUERPO del pedido. Aca la organizacion sale
del Workspace de la URL y el permiso pasa por `apps/workspaces/permissions.py`,
como todo el resto. El endpoint viejo quedo delegando en esta misma resolucion
para que no haya dos puertas con reglas distintas.

Vive en su propio archivo por lo mismo que `gallery.py` y `admin_agents.py`:
`views.py` de esta app ya carga con el chat, los documentos y los disparadores.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone as _tz

from apps.organizations.models import SystemConnection
from apps.workspaces.models import ROLE_ADMIN
from apps.workspaces.permissions import require_membership, workspaces_visible_to

from .gallery import puede_editar_agentes
from .models import Agent, AgentConfig, Skill

# Lo que el formulario puede escribir. `handle`, `organization` y `created_by` no
# estan a proposito: los pone el servidor.
CAMPOS_TEXTO = ('name', 'description', 'instructions', 'area', 'model', 'tools_summary',
                'recommended_frequency')

# Lo que la empresa le entrega a ESTE agente (el modelo `AgentConfig`). Estaba en
# una pantalla aparte, Admin > Agentes, asi que habia dos lugares distintos para
# configurar un mismo agente. Se atienden aca, pero SOLO para administradores: sigue
# siendo una decision de la empresa y no de quien construye el agente.
CAMPOS_DE_EMPRESA = ('datos', 'reglas', 'info_util')

LARGOS = {
    'name': 255,
    'description': 4000,
    'instructions': 20000,
    'area': 30,
    'model': 120,
    'tools_summary': 280,
    'recommended_frequency': 60,
    'datos': 4000,
    'reglas': 4000,
    'info_util': 4000,
}


class NoPuedeCrear(Exception):
    """La politica del Workspace no deja a esta persona crear ni editar agentes."""


def _membership_que_edita(user, slug):
    """El membership de quien pide, ya comprobado que puede tocar agentes.

    `require_membership` corta con 404 si no es miembro (no 403: no tiene por que
    saber que el Workspace existe). Que sea miembro pero la politica no lo
    habilite si es un 403 — la diferencia importa.
    """
    membership = require_membership(user, slug)
    if not puede_editar_agentes(membership):
        raise NoPuedeCrear(
            'En este Workspace solo los editores y administradores crean agentes. '
            'Pidele a un administrador que cambie quien puede crearlos, o que lo cree por ti.'
        )
    return membership


def _limpiar_de_empresa(datos):
    """Los tres campos de `AgentConfig` que vengan en el pedido, recortados."""
    limpio = {}
    for campo in CAMPOS_DE_EMPRESA:
        if campo in datos:
            valor = datos.get(campo) or ''
            if not isinstance(valor, str):
                valor = str(valor)
            limpio[campo] = valor.strip()[:LARGOS[campo]]
    return limpio


def _guardar_config(agent, datos, user):
    """Guarda lo que la empresa le entrega al agente y recalcula si esta configurado.

    Queda "configurado" en cuanto se le entrego algo, y vaciarlo todo lo devuelve a
    pendiente: es informacion de la empresa, no una casilla que se marca.
    """
    campos = _limpiar_de_empresa(datos)
    if not campos:
        return
    config, _ = AgentConfig.objects.get_or_create(agent=agent)
    for campo, valor in campos.items():
        setattr(config, campo, valor)
    tiene_algo = any([config.datos, config.reglas, config.info_util])
    if tiene_algo and not config.completed_at:
        config.completed_at = _tz.now()
    elif not tiene_algo:
        config.completed_at = None
    config.updated_by = user
    config.save()


def _limpiar(datos):
    """Los campos de texto, recortados y con tope de largo.

    El tope se aplica aca y no solo en el modelo porque `instructions` es un
    TextField sin limite: sin esto, pegar un libro entero en las instrucciones se
    guarda y despues entra en cada respuesta del agente.
    """
    limpio = {}
    for campo in CAMPOS_TEXTO:
        if campo not in datos:
            continue
        valor = (datos.get(campo) or '')
        if not isinstance(valor, str):
            valor = str(valor)
        limpio[campo] = valor.strip()[:LARGOS[campo]]
    return limpio


def _serializar(agent, detalle=True):
    datos = {
        'id': agent.id,
        'name': agent.name,
        'handle': agent.handle,
        'description': agent.description,
        'area': agent.area,
        'model': agent.model,
        'is_active': agent.is_active,
    }
    if detalle:
        datos.update({
            'instructions': agent.instructions,
            'tools_summary': agent.tools_summary,
            'recommended_frequency': agent.recommended_frequency,
            'system_ids': sorted(agent.systems.values_list('id', flat=True)),
            'skill_ids': sorted(agent.skills.values_list('id', flat=True)),
            'space_ids': sorted(agent.workspaces.values_list('id', flat=True)),
        })
        config = getattr(agent, 'config', None)
        datos.update({
            'datos': config.datos if config else '',
            'reglas': config.reglas if config else '',
            'info_util': config.info_util if config else '',
            'configurado': bool(config and config.esta_configurado),
        })
    return datos


def _enganchar(agent, datos, membership):
    """Sistemas, Habilidades y Espacios del agente.

    Cada coleccion se filtra por la empresa o el Workspace de quien pide: mandar
    el id de un sistema de otra empresa no engancha nada en vez de fallar, que es
    la misma regla que ya usan las Habilidades y los Espacios.

    Una clave ausente no se toca (asi un PATCH parcial no borra lo que no nombro);
    una lista vacia si vacia la coleccion.
    """
    org_id = membership.organization_id

    if 'system_ids' in datos:
        agent.systems.set(SystemConnection.objects.filter(
            organization_id=org_id, pk__in=_ids(datos['system_ids']),
        ))
    if 'skill_ids' in datos:
        agent.skills.set(Skill.objects.filter(
            organization_id=org_id, pk__in=_ids(datos['skill_ids']),
        ))
    if 'space_ids' in datos:
        # Solo Espacios que esta persona ve: si no, se podria meter un agente en un
        # Espacio restringido ajeno y con eso alcanzar sus datos.
        visibles = workspaces_visible_to(membership).filter(pk__in=_ids(datos['space_ids']))
        agent.workspaces.set(visibles)


def _ids(valor):
    """Una lista de ids desde lo que haya mandado el formulario."""
    if not isinstance(valor, (list, tuple)):
        return []
    limpios = []
    for v in valor:
        try:
            limpios.append(int(v))
        except (TypeError, ValueError):
            continue
    return limpios


class OpcionesConstructorView(APIView):
    """GET /api/v1/agents/constructor/opciones/?workspace=<slug>

    Todo lo que el formulario necesita para armarse, en un solo viaje: los modelos
    de IA disponibles, los sistemas conectados, las Habilidades y los Espacios.
    Separado en cuatro llamadas, la pantalla se dibujaba a pedazos.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = require_membership(request.user, slug)
        org_id = membership.organization_id

        from .views import modelos_disponibles

        return Response({
            'puede_crear': puede_editar_agentes(membership),
            # Lo que la empresa le entrega al agente (datos/reglas/info) es decision
            # de la empresa: el formulario solo lo muestra a un administrador.
            'puede_configurar_empresa': membership.role == ROLE_ADMIN,
            'modelos': modelos_disponibles(),
            'sistemas': [
                {'id': c.id, 'name': c.name, 'connector_type': c.connector_type}
                for c in SystemConnection.objects.filter(
                    organization_id=org_id, is_active=True,
                ).order_by('name')
            ],
            'habilidades': [
                {'id': s.id, 'name': s.name, 'description': s.description}
                for s in Skill.objects.filter(
                    organization_id=org_id, is_active=True,
                ).order_by('name')
            ],
            'espacios': [
                {'id': e.id, 'name': e.name, 'slug': e.slug, 'visibility': e.visibility}
                for e in workspaces_visible_to(membership).order_by('name')
            ],
        })


class AgenteConstructorListCreateView(APIView):
    """POST /api/v1/agents/constructor/ — crear un agente."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        slug = request.data.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = _membership_que_edita(request.user, slug)
        except NoPuedeCrear as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)

        campos = _limpiar(request.data)
        if not campos.get('name'):
            return Response(
                {'detail': 'El agente necesita un nombre.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        org_id = membership.organization_id
        if Agent.objects.filter(organization_id=org_id, name__iexact=campos['name']).exists():
            return Response(
                {'detail': f'Ya existe un agente llamado «{campos["name"]}» en esta empresa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ⭐ De dónde cuelga. Es lo que impide volver al formulario en blanco: un agente
        # nuevo nace sobre material que ya existe —una carpeta con documentos o una
        # herramienta conectada— y nunca sobre la nada. La carpeta además le da el alcance
        # y los permisos sin preguntarle nada al usuario.
        carpeta = None
        if request.data.get('carpeta'):
            from apps.archivos.models import Carpeta
            from apps.archivos.permisos import NIVEL_EDICION, nivel_sobre_carpeta

            carpeta = Carpeta.objects.filter(
                organization_id=org_id, pk=request.data['carpeta'],
            ).first()
            if carpeta is None:
                return Response({'detail': 'No encuentro esa carpeta.'},
                                status=status.HTTP_404_NOT_FOUND)
            if nivel_sobre_carpeta(request.user, carpeta, membership) != NIVEL_EDICION:
                return Response({'detail': 'No puedes crear un agente en esa carpeta.'},
                                status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            agent = Agent.objects.create(
                organization_id=org_id, created_by=request.user, carpeta=carpeta, **campos,
            )
            _enganchar(agent, request.data, membership)
            # Nace pendiente en Admin > Agentes: la empresa todavia no le dijo con
            # que datos y reglas trabaja. Es el mismo camino que un agente cargado
            # desde una plantilla.
            AgentConfig.objects.get_or_create(agent=agent)
            if membership.role == ROLE_ADMIN:
                _guardar_config(agent, request.data, request.user)

        return Response(_serializar(agent), status=status.HTTP_201_CREATED)


class AgenteConstructorDetailView(APIView):
    """GET y PATCH /api/v1/agents/constructor/<pk>/ — editar un agente."""

    permission_classes = [IsAuthenticated]

    def _agente(self, request, pk):
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return None, None, Response(
                {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            membership = _membership_que_edita(request.user, slug)
        except NoPuedeCrear as e:
            return None, None, Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)

        agent = Agent.objects.filter(
            pk=pk, organization_id=membership.organization_id,
        ).first()
        if agent is None:
            return None, None, Response(
                {'detail': 'Agente no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return agent, membership, None

    def get(self, request, pk):
        agent, _, error = self._agente(request, pk)
        if error:
            return error
        return Response(_serializar(agent))

    def patch(self, request, pk):
        agent, membership, error = self._agente(request, pk)
        if error:
            return error

        campos = _limpiar(request.data)
        if 'name' in campos:
            if not campos['name']:
                return Response(
                    {'detail': 'El agente necesita un nombre.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            choca = Agent.objects.filter(
                organization_id=membership.organization_id,
                name__iexact=campos['name'],
            ).exclude(pk=agent.pk).exists()
            if choca:
                return Response(
                    {'detail': f'Ya existe un agente llamado «{campos["name"]}» en esta empresa.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            for campo, valor in campos.items():
                setattr(agent, campo, valor)
            # El handle NO se recalcula al renombrar: es con lo que se lo menciona en
            # las conversaciones y cambiarlo rompe los hilos que ya lo nombran.
            agent.save()
            _enganchar(agent, request.data, membership)
            # Los tres campos de empresa solo los toca un administrador: mandarlos
            # sin ese rol no falla, simplemente no se guardan (el formulario tampoco
            # los muestra).
            if membership.role == ROLE_ADMIN:
                _guardar_config(agent, request.data, request.user)

        return Response(_serializar(agent))
