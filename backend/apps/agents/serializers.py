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
        # `handle` lo genera `Agent.save()` desde el nombre y no se recalcula al
        # renombrar: es la identidad con la que se lo menciona en las conversaciones.
        # Estaba escribible y ademas salia como REQUERIDO, asi que un POST sin handle
        # fallaba con 400 — parte de por que este endpoint no lo llamaba nadie.
        read_only_fields = ['id', 'handle', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    # Firmado por mensaje, no por conversacion: en un hilo pueden haber
    # contestado varios agentes y al recargar hay que poder distinguirlos.
    agent_name = serializers.CharField(source='agent.name', read_only=True, default=None)
    agent_handle = serializers.CharField(source='agent.handle', read_only=True, default=None)
    # Quien lo escribio. En un hilo de equipo, sin esto todas las preguntas parecen de la
    # misma persona.
    autor = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'agent', 'agent_name', 'agent_handle',
                  'autor', 'fuentes', 'artefactos', 'model_used', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_autor(self, obj):
        if obj.user is None:
            return None
        return {
            'id': obj.user.id,
            'nombre': obj.user.get_full_name() or obj.user.email.split('@')[0],
            'email': obj.user.email,
        }


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
    # La Sesión en la que vive el hilo, si está compartido. La barra lateral la usa para
    # distinguir de un vistazo lo personal de lo que ve el equipo.
    sesion_nombre = serializers.CharField(source='sesion.name', read_only=True, default=None)
    sesion_slug = serializers.CharField(source='sesion.slug', read_only=True, default=None)

    class Meta:
        model = Conversation
        fields = ['id', 'agent', 'agent_name', 'title', 'last_message',
                  'sesion', 'sesion_nombre', 'sesion_slug', 'created_at', 'updated_at']

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

    def validate_name(self, value):
        """El nombre no se repite dentro de la misma empresa.

        La base ya lo impedía (`unico_nombre_de_habilidad_por_empresa`), pero sin esta
        validación la restricción saltaba como IntegrityError y la persona veía un error
        del sistema en vez de "ya tiene una Habilidad con ese nombre". Un choque de
        nombres es un caso normal, no una falla.
        """
        nombre = value.strip()
        organizacion = self.context.get('organization')
        if not nombre or organizacion is None:
            return nombre

        repetidas = Skill.objects.filter(organization=organizacion, name__iexact=nombre)
        if self.instance is not None:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError('Ya tiene una Habilidad con ese nombre.')
        return nombre


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
    sesion_name = serializers.CharField(source='sesion.name', read_only=True)
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = Automation
        fields = ['id', 'organization', 'name', 'prompt', 'interval_minutes', 'notify_email',
                  'schedule_config', 'webhook_url', 'disparador',
                  'sesion', 'sesion_name', 'crear_tarea', 'agent', 'agent_name',
                  'is_active', 'trigger_type', 'connection', 'connection_name', 'event_type',
                  'event_config', 'last_run_at', 'last_result', 'last_error', 'run_count', 'created_at']
        read_only_fields = ['id', 'connection_name', 'webhook_url', 'disparador',
                            'sesion_name', 'agent_name',
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

        # Un encargo cuyo resultado no va a ninguna parte no es un encargo. Antes el
        # correo era obligatorio y esto no podía pasar; desde que se puede publicar en una
        # Sesión, se puede quedar sin ninguno de los dos.
        if not get('notify_email').strip() and not get('sesion', None):
            raise serializers.ValidationError({
                'notify_email': 'Di a dónde llega el resultado: un correo, una Sesión, o los dos.',
            })

        # La Sesión tiene que ser del Workspace de esta empresa. Sin esto, alguien podría
        # hacer publicar a un agente en la Sesión de otra empresa mandando un id.
        sesion = get('sesion', None)
        if sesion is not None:
            org = get('organization', None)
            org_id = getattr(org, 'pk', org)
            if sesion.workspace.organization_id != org_id:
                raise serializers.ValidationError({
                    'sesion': 'Esa Sesión no es de esta empresa.',
                })
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
