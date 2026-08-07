from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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
    ])),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
