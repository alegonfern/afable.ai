from django.urls import path
from .banco_de_pruebas import BancoDePruebasView
from .views import (
    OrganizationListCreateView, OrganizationDetailView,
    OdooIntegrationView, OdooTestConnectionView, IntegrationScanListView,
    ActiveIntegrationListView, ConnectIntegrationView, DisconnectIntegrationView,
    SystemConnectionListCreateView, SystemConnectionDetailView,
    SystemConnectionTestView, SystemConnectionSyncView,
    CatalogoDeConectoresView, SystemConnectionEstadoView,
    OrganizationDashboardView, BusinessModelView,
    OrganizationContextView, CompanyDocumentListCreateView, CompanyDocumentDetailView,
    ContextCubicleListCreateView, ContextCubicleDetailView, ContextMarkdownView,
    RequestIntegrationView,
    GoogleDriveConnectStartView, GoogleDriveConnectCallbackView,
    GoogleDriveAccessTokenView, GoogleDriveFilesView, GoogleDriveFolderView,
)

urlpatterns = [
    path('', OrganizationListCreateView.as_view(), name='organization-list'),
    path('scans/', IntegrationScanListView.as_view(), name='integration-scans'),
    path('integrations/', ActiveIntegrationListView.as_view(), name='active-integrations'),
    path('integrations/connect/', ConnectIntegrationView.as_view(), name='connect-integration'),
    path('integrations/disconnect/', DisconnectIntegrationView.as_view(), name='disconnect-integration'),
    path('integrations/request/', RequestIntegrationView.as_view(), name='request-integration'),
    # SystemConnection — conectores genéricos (Odoo, SAP/MSSQL, PostgreSQL, CSV)
    path('dashboard/', OrganizationDashboardView.as_view(), name='org-dashboard'),
    path('model/', BusinessModelView.as_view(), name='org-model'),
    # Banco de pruebas: recorrer estados del producto sin armarlos a mano. Solo para los
    # correos de `settings.CUENTAS_DE_PRUEBA`, vacío en producción.
    path('banco-de-pruebas/', BancoDePruebasView.as_view(), name='banco-de-pruebas'),
    path('connections/', SystemConnectionListCreateView.as_view(), name='system-connections'),
    # Qué se puede conectar y qué se gana con cada cosa. Es la ficha, no la lista de
    # claves técnicas: quien elige acá no sabe qué es «mssql».
    path('connections/catalogo/', CatalogoDeConectoresView.as_view(), name='connector-catalog'),
    path('connections/<int:pk>/estado/', SystemConnectionEstadoView.as_view(), name='system-connection-state'),
    path('connections/google-drive/start/', GoogleDriveConnectStartView.as_view(), name='google-drive-start'),
    path('connections/google-drive/callback/', GoogleDriveConnectCallbackView.as_view(), name='google-drive-callback'),
    path('connections/<int:pk>/', SystemConnectionDetailView.as_view(), name='system-connection-detail'),
    path('connections/<int:pk>/test/', SystemConnectionTestView.as_view(), name='system-connection-test'),
    path('connections/<int:pk>/sync/', SystemConnectionSyncView.as_view(), name='system-connection-sync'),
    path('connections/<int:pk>/google-drive/access-token/', GoogleDriveAccessTokenView.as_view(), name='google-drive-access-token'),
    path('connections/<int:pk>/google-drive/folder/', GoogleDriveFolderView.as_view(), name='google-drive-folder'),
    path('connections/<int:pk>/google-drive/files/', GoogleDriveFilesView.as_view(), name='google-drive-files'),
    path('<int:pk>/', OrganizationDetailView.as_view(), name='organization-detail'),
    path('<int:pk>/integrations/odoo/', OdooIntegrationView.as_view(), name='odoo-integration'),
    path('<int:pk>/integrations/odoo/test/', OdooTestConnectionView.as_view(), name='odoo-test'),
    path('<int:pk>/context/', OrganizationContextView.as_view(), name='organization-context'),
    path('<int:pk>/documents/', CompanyDocumentListCreateView.as_view(), name='company-documents'),
    path('<int:pk>/documents/<int:doc_id>/', CompanyDocumentDetailView.as_view(), name='company-document-detail'),
    path('<int:pk>/context-cubicles/markdown/', ContextMarkdownView.as_view(), name='context-cubicles-markdown'),
    path('<int:pk>/context-cubicles/<int:cubicle_id>/', ContextCubicleDetailView.as_view(), name='context-cubicle-detail'),
    path('<int:pk>/context-cubicles/', ContextCubicleListCreateView.as_view(), name='context-cubicles'),
]
