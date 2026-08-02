from django.urls import path

from .views import LeadChatView

urlpatterns = [
    path('chat/', LeadChatView.as_view(), name='lead-chat'),
]
