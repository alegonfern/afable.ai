"""El banco de pruebas: recorrer el producto sin reconstruir el estado a mano cada vez.

Probar Afable de punta a punta significa llegar a estados que cuestan trabajo armar: una
empresa recién creada sin nada, una con carpetas llenas y sin agentes, una con documentos
esperando aprobación. Reproducir cada uno a mano son diez minutos de clics, y por eso en la
práctica no se prueban — se prueba lo que es fácil de llegar, que no es donde están los
errores.

Esto pone cada estado a un botón.

## Qué NO es

No es un modo demo ni una pantalla de administración. **No falsea nada**: cada acción usa
exactamente el mismo código que usaría un usuario real. Cargar la empresa de ejemplo llama a
`crear_para`, armar la estructura llama a `crear_estructura`. Si una de esas funciones se
rompe, esta pantalla se rompe igual — que es justamente lo que se quiere, porque probar
contra un camino distinto del real no prueba nada.

## Quién entra

Solo los correos de `settings.CUENTAS_DE_PRUEBA`, y solo sobre su propia empresa.

⚠️ **Es una lista de correos y no `is_staff`.** Un flag de Django se otorga sin pensarlo —al
crear un superusuario, al depurar algo un martes— y acá hay acciones que borran carpetas
enteras. Una lista hay que editarla a mano, y quien la edita sabe qué está habilitando. En
producción viene vacía: nadie entra salvo que se ponga el correo en el `.env`.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import require_membership


def es_cuenta_de_pruebas(user):
    correo = (getattr(user, 'email', '') or '').strip().lower()
    return bool(correo) and correo in getattr(settings, 'CUENTAS_DE_PRUEBA', [])


def _estado(organization, usuario, membership):
    """Qué hay ahora mismo. Es lo primero que se mira antes de tocar un botón."""
    from apps.agents.models import Agent, Automation, Conversation
    from apps.archivos.models import PUBLICACION_PENDIENTE, Carpeta, SolicitudDePublicacion
    from apps.workspaces.models import Membership
    from services.recomendaciones import para

    from .models import CompanyDocument, SystemConnection

    return {
        'empresa': organization.name,
        'carpetas': Carpeta.objects.filter(organization=organization, personal=False).count(),
        'carpetas_personales': Carpeta.objects.filter(
            organization=organization, personal=True,
        ).count(),
        'documentos': CompanyDocument.objects.filter(organization=organization).count(),
        'documentos_de_ejemplo': CompanyDocument.objects.filter(
            organization=organization, source='ejemplo',
        ).count(),
        'agentes': Agent.objects.filter(organization=organization).count(),
        'agentes_con_carpeta': Agent.objects.filter(
            organization=organization, carpeta__isnull=False,
        ).count(),
        'conectores': SystemConnection.objects.filter(organization=organization).count(),
        'personas': Membership.objects.filter(organization=organization).count(),
        'conversaciones': Conversation.objects.filter(
            agent__organization=organization,
        ).count(),
        'automatizaciones': Automation.objects.filter(organization=organization).count(),
        'publicaciones_pendientes': SolicitudDePublicacion.objects.filter(
            destino__organization=organization, estado=PUBLICACION_PENDIENTE,
        ).count(),
        # Lo que el usuario vería ahora en el chat. Es la forma rápida de comprobar que las
        # recomendaciones reaccionan al estado sin tener que abrir la otra pantalla.
        'recomendaciones': [r['texto'] for r in para(organization, usuario, membership)],
    }


class BancoDePruebasView(APIView):
    """GET — el estado actual. POST — ejecutar una acción."""

    permission_classes = [IsAuthenticated]

    ACCIONES = {
        'cargar_demo': 'Carga una de las tres empresas de ejemplo',
        'quitar_demo': 'Saca los documentos de ejemplo y su Workspace',
        'armar_estructura': 'Crea la carpeta de la empresa y su árbol, según el rubro',
        'vaciar_estructura': 'Borra las carpetas de la empresa (no las personales)',
        'reiniciar_onboarding': 'Vuelve a mostrar los primeros pasos',
        'disparar_automatizaciones': 'Corre las automatizaciones vencidas sin esperar',
    }

    def _acceso(self, request):
        if not es_cuenta_de_pruebas(request.user):
            return None, Response(
                {'detail': 'Esta pantalla no está disponible para su cuenta.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        slug = request.data.get('workspace') or request.query_params.get('workspace')
        if not slug:
            return None, Response(
                {'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        return require_membership(request.user, slug), None

    def get(self, request):
        membership, error = self._acceso(request)
        if error:
            return error
        return Response({
            'acciones': [{'clave': k, 'que_hace': v} for k, v in self.ACCIONES.items()],
            'estado': _estado(membership.organization, request.user, membership),
        })

    def post(self, request):
        membership, error = self._acceso(request)
        if error:
            return error

        accion = request.data.get('accion')
        if accion not in self.ACCIONES:
            return Response(
                {'detail': f'No conozco la acción «{accion}».'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = membership.organization
        resultado = getattr(self, f'_{accion}')(request, organization)

        return Response({
            'hecho': resultado,
            'estado': _estado(organization, request.user, membership),
        })

    # ── las acciones ─────────────────────────────────────────────────────────

    def _cargar_demo(self, request, organization):
        from .datos_de_ejemplo import DISTRIBUIDORA, crear_para

        tipo = request.data.get('tipo') or DISTRIBUIDORA
        _, creados = crear_para(organization, request.user, tipo=tipo)
        return f'Cargada la empresa «{tipo}»: {creados} documentos nuevos.'

    def _quitar_demo(self, request, organization):
        from .datos_de_ejemplo import quitar_de

        return f'Quitados {quitar_de(organization)} documentos de ejemplo.'

    def _armar_estructura(self, request, organization):
        from services.estructura_inicial import crear_estructura

        rubro = request.data.get('rubro') or 'general'
        root = crear_estructura(organization, rubro, request.user)
        return f'Armada «{root.name}» con el árbol de {rubro}.'

    def _vaciar_estructura(self, request, organization):
        """Deja la empresa como recién creada, para volver a probar el arranque.

        ⚠️ No toca las carpetas personales. Lo de cada uno es de cada uno, incluso en una
        pantalla de pruebas — y borrarlas obligaría a recrear usuarios para volver a
        probar, que es justo el trabajo manual que esto viene a evitar.
        """
        from apps.archivos.models import Carpeta

        borradas, _ = Carpeta.objects.filter(
            organization=organization, personal=False,
        ).delete()
        return f'Borradas las carpetas de la empresa ({borradas} filas en total).'

    def _reiniciar_onboarding(self, request, organization):
        # El campo vive en la Empresa, no en el Workspace (`primeros_pasos.py:188`).
        organization.onboarding_oculto = False
        organization.save(update_fields=['onboarding_oculto', 'updated_at'])
        return 'Los primeros pasos vuelven a aparecer.'

    def _disparar_automatizaciones(self, request, organization):
        """Corre lo vencido sin esperar el intervalo.

        Sin esto, probar una automatización horaria es esperar una hora — así que en la
        práctica no se prueban.
        """
        from django.core.management import call_command

        call_command('run_automations', once=True)
        return 'Corrida una pasada del corredor.'
