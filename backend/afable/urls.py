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
        path('invitations/', include('apps.workspaces.invitation_urls')),
        path('organizations/', include('apps.organizations.urls')),
        path('sources/', include('apps.sources.urls')),
        path('agents/', include('apps.agents.urls')),
        path('sesiones/', include('apps.sesiones.urls')),
        path('tools/', include('apps.tools.urls')),
        path('payments/', include('apps.payments.urls')),
        path('leads/', include('apps.leads.urls')),
    ])),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
