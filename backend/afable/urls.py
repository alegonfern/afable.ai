from django.contrib import admin
from django.urls import path, include
from django.conf import settings


def _media_publica():
    """Sirve por `/media/` SOLO lo que es público de verdad: logos y fotos de perfil.

    ⚠️ Los documentos de empresa quedan fuera a propósito. Se entregaban a cualquiera que
    tuviera la dirección, sin sesión — ahora salen por
    `/api/v1/archivos/documentos/<id>/archivo/`, que comprueba permisos.

    ⚠️ **Esto cubre lo que sirve Django.** Si en el servidor hay un nginx publicando
    `/media/` por su cuenta, hay que cerrarle `company_documents/` ahí también: este
    archivo no lo alcanza.
    """
    from django.urls import re_path
    from django.views.static import serve

    if not settings.DEBUG:
        return []
    return [
        re_path(
            r'^media/(?P<path>(?!company_documents/).*)$',
            serve, {'document_root': settings.MEDIA_ROOT},
        ),
    ]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include([
        path('auth/', include('apps.authentication.urls')),
        path('user/', include('apps.authentication.user_urls')),
        path('workspaces/', include('apps.workspaces.urls')),
        # La facturación es del Workspace, así que su slug va en la URL como en todo
        # lo demás de la empresa. Vive en `apps.payments` porque ahí están los
        # modelos y las pasarelas; sólo el ruteo se cuelga de `workspaces/`.
        path('workspaces/', include('apps.payments.facturacion_urls')),
        path('invitations/', include('apps.workspaces.invitation_urls')),
        path('organizations/', include('apps.organizations.urls')),
        path('sources/', include('apps.sources.urls')),
        path('archivos/', include('apps.archivos.urls')),
        path('agents/', include('apps.agents.urls')),
        path('sesiones/', include('apps.sesiones.urls')),
        # Las tareas cruzando Sesiones. Va en la raíz y no bajo `sesiones/` porque la
        # pregunta que contesta —"¿qué tengo pendiente?"— no es sobre una Sesión.
        path('tareas/', include('apps.sesiones.tareas_urls')),
        path('tools/', include('apps.tools.urls')),
        path('payments/', include('apps.payments.urls')),
        path('leads/', include('apps.leads.urls')),
        path('soporte/', include('apps.soporte.urls')),
        path('notificaciones/', include('apps.notificaciones.urls')),
    ])),
] + _media_publica()
