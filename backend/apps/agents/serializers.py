from rest_framework import serializers
from .models import (
    Agent, AgentTemplate, Conversation, Message, Document, Automation, Routine, Skill,
)


class AgentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTemplate
        fields = ['id', 'name', 'description', 'instructions', 'area', 'model',
                  'tools_summary', 'recommended_frequency',
                  'category', 'icon', 'accent', 'flow', 'author_name', 'kind',
                  'uses_count', 'is_featured', 'created_at']
        read_only_fields = fields


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ['id', 'organization', 'name', 'handle', 'description', 'instructions',
                  'area', 'systems', 'model', 'tools_summary',
                  'recommended_frequency', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    # Firmado por mensaje, no por conversacion: en un hilo pueden haber
    # contestado varios agentes y al recargar hay que poder distinguirlos.
    agent_name = serializers.CharField(source='agent.name', read_only=True, default=None)
    agent_handle = serializers.CharField(source='agent.handle', read_only=True, default=None)

    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'agent', 'agent_name', 'agent_handle',
                  'model_used', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    # El chat necesita saber de quién es el hilo al abrirlo desde el historial,
    # para que el selector muestre el agente correcto y no el que quedó de la
    # conversación anterior.
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'agent', 'agent_name', 'title', 'messages', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationListSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'agent', 'agent_name', 'title', 'last_message', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg:
            return {'role': msg.role, 'content': msg.content[:100], 'created_at': msg.created_at}
        return None


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class SkillSerializer(serializers.ModelSerializer):
    """La Habilidad como fila: incluye a quiénes se les aplica."""

    agents = serializers.SerializerMethodField()

    class Meta:
        model = Skill
        fields = ['id', 'name', 'description', 'instructions', 'agents',
                  'is_active', 'created_at', 'updated_at']

    def get_agents(self, obj):
        return [{'id': a.id, 'name': a.name, 'handle': a.handle} for a in obj.agents.all()]


class SkillWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['name', 'description', 'instructions', 'is_active']

    def validate_instructions(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                'Una Habilidad sin instrucciones no le agrega nada al agente.'
            )
        return value


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'content', 'conversation', 'grid_x', 'grid_y', 'grid_w', 'grid_h', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AutomationSerializer(serializers.ModelSerializer):
    # La URL completa, no el token pelado: lo que el usuario tiene que pegar en el
    # otro sistema es la dirección, y armarla a mano es una fuente de errores.
    webhook_url = serializers.SerializerMethodField()
    # Cuándo corre, en castellano, para no tener que interpretar el JSON en la pantalla.
    disparador = serializers.CharField(source='descripcion_del_disparador', read_only=True)

    def get_webhook_url(self, obj):
        if obj.trigger_type != 'webhook' or not obj.webhook_token:
            return None
        ruta = f'/api/v1/agents/webhooks/{obj.webhook_token}/'
        request = self.context.get('request')
        return request.build_absolute_uri(ruta) if request else ruta

    connection_name = serializers.CharField(source='connection.name', read_only=True)

    class Meta:
        model = Automation
        fields = ['id', 'organization', 'name', 'prompt', 'interval_minutes', 'notify_email',
                  'schedule_config', 'webhook_url', 'disparador',
                  'is_active', 'trigger_type', 'connection', 'connection_name', 'event_type',
                  'event_config', 'last_run_at', 'last_result', 'last_error', 'run_count', 'created_at']
        read_only_fields = ['id', 'connection_name', 'webhook_url', 'disparador',
                            'last_run_at', 'last_result', 'last_error',
                            'run_count', 'created_at']

    def validate_interval_minutes(self, value):
        if value < 5:
            raise serializers.ValidationError('El intervalo mínimo es 5 minutos.')
        return value

    def validate(self, data):
        get = lambda f, default='': data.get(f, getattr(self.instance, f, default) if self.instance else default)
        if get('trigger_type', 'interval') == 'event':
            if not get('connection', None):
                raise serializers.ValidationError({'connection': 'Elige qué conexión vigilar.'})
            if not get('event_type'):
                raise serializers.ValidationError({'event_type': 'Elige el tipo de evento.'})
            if get('event_type') == 'new_rows' and not (get('event_config', {}) or {}).get('table', '').strip():
                raise serializers.ValidationError({'event_config': 'Indica la tabla (o modelo Odoo) a vigilar.'})
        elif not get('prompt').strip():
            raise serializers.ValidationError({'prompt': 'El prompt es obligatorio en las programadas.'})
        return data


class RoutineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Routine
        fields = ['id', 'organization', 'name', 'steps', 'interval_minutes', 'notify_email',
                  'is_active', 'last_run_at', 'last_steps_results', 'last_error', 'run_count', 'created_at']
        read_only_fields = ['id', 'last_run_at', 'last_steps_results', 'last_error', 'run_count', 'created_at']

    def validate_interval_minutes(self, value):
        if value is not None and value < 5:
            raise serializers.ValidationError('El intervalo mínimo es 5 minutos.')
        return value

    def validate_steps(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('steps debe ser una lista de pasos.')
        if not any((s.get('prompt') or '').strip() for s in value if isinstance(s, dict)):
            raise serializers.ValidationError('La rutina necesita al menos un paso con prompt.')
        if len(value) > 10:
            raise serializers.ValidationError('Máximo 10 pasos por rutina.')
        return value
