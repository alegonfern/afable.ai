from django.contrib import admin
from .models import Agent, Conversation, Message


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'erp_type', 'is_active', 'created_at']
    list_filter = ['erp_type', 'is_active']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'agent', 'user', 'created_at']
    raw_id_fields = ['agent', 'user']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'created_at']
    list_filter = ['role']
