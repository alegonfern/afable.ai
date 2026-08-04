from django.urls import path
from .views import (
    SkillDetailView, SkillListCreateView,
    ConversationBranchView, MessageEditView, AutomationWebhookView,
    AgentListCreateView, AgentDetailView, AvailableModelsView,
    AgentTemplateListView, AgentTemplateUseView,
    ChatView, DirectChatView, DirectChatStreamView, ChatAttachmentView,
    ConversationListView, ConversationDetailView,
    UserConversationListView, UserConversationDetailView,
    DocumentListCreateView, DocumentDetailView,
    AutomationListCreateView, AutomationDetailView, AutomationRunNowView,
    RoutineListCreateView, RoutineDetailView, RoutineRunNowView,
)
from .gallery import AgentFavoriteView, AgentGalleryView
from .admin_agents import AgenteAdminDetailView, AgentesAdminListView
from .builder import (
    AgenteConstructorDetailView, AgenteConstructorListCreateView, OpcionesConstructorView,
)

urlpatterns = [
    path('', AgentListCreateView.as_view(), name='agent-list'),
    path('models/', AvailableModelsView.as_view(), name='available-models'),
    # La galeria de Agentes de la vista Trabajo (Favoritos / Todos / Editables por mi).
    path('gallery/', AgentGalleryView.as_view(), name='agent-gallery'),
    # Constructor: crear y editar un agente desde la app, sin codigo.
    path('constructor/', AgenteConstructorListCreateView.as_view(), name='agent-builder'),
    path('constructor/opciones/', OpcionesConstructorView.as_view(), name='agent-builder-options'),
    path('constructor/<int:pk>/', AgenteConstructorDetailView.as_view(), name='agent-builder-detail'),
    # Admin > Agentes: que datos, reglas e informacion le entrega la empresa.
    path('admin/', AgentesAdminListView.as_view(), name='agent-admin-list'),
    path('admin/<int:pk>/', AgenteAdminDetailView.as_view(), name='agent-admin-detail'),
    path('<int:pk>/favorite/', AgentFavoriteView.as_view(), name='agent-favorite'),
    path('templates/', AgentTemplateListView.as_view(), name='agent-templates'),
    path('templates/<int:pk>/use/', AgentTemplateUseView.as_view(), name='agent-template-use'),
    path('documents/', DocumentListCreateView.as_view(), name='document-list'),
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document-detail'),
    path('habilidades/', SkillListCreateView.as_view(), name='skill-list'),
    path('habilidades/<int:pk>/', SkillDetailView.as_view(), name='skill-detail'),
    # Lo llama un sistema de afuera; el token es la credencial (ver la vista).
    path('webhooks/<str:token>/', AutomationWebhookView.as_view(), name='automation-webhook'),
    path('automations/', AutomationListCreateView.as_view(), name='automation-list'),
    path('automations/<int:pk>/', AutomationDetailView.as_view(), name='automation-detail'),
    path('automations/<int:pk>/run/', AutomationRunNowView.as_view(), name='automation-run'),
    path('routines/', RoutineListCreateView.as_view(), name='routine-list'),
    path('routines/<int:pk>/', RoutineDetailView.as_view(), name='routine-detail'),
    path('routines/<int:pk>/run/', RoutineRunNowView.as_view(), name='routine-run'),
    path('direct-chat/', DirectChatView.as_view(), name='direct-chat'),
    path('direct-chat/stream/', DirectChatStreamView.as_view(), name='direct-chat-stream'),
    path('chat-attachment/', ChatAttachmentView.as_view(), name='chat-attachment'),
    path('conversations/', UserConversationListView.as_view(), name='user-conversations'),
    path('conversations/<int:conv_id>/', UserConversationDetailView.as_view(), name='user-conversation-detail'),
    path('conversations/<int:conv_id>/messages/', UserConversationDetailView.as_view(), name='user-conversation-messages'),
    path(
        'conversations/<int:conv_id>/ramificar/',
        ConversationBranchView.as_view(), name='conversation-branch',
    ),
    path(
        'conversations/<int:conv_id>/messages/<int:message_id>/',
        MessageEditView.as_view(), name='message-edit',
    ),
    path('<int:pk>/', AgentDetailView.as_view(), name='agent-detail'),
    path('<int:pk>/chat/', ChatView.as_view(), name='agent-chat'),
    path('<int:pk>/conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('<int:pk>/conversations/<int:conv_id>/', ConversationDetailView.as_view(), name='conversation-detail'),
]
