from rest_framework import serializers
from .models import (
    Organization, IntegrationScan, ActiveIntegration, SystemConnection,
    OrganizationContext, CompanyDocument, ContextCubicle,
)


class OrganizationSerializer(serializers.ModelSerializer):
    # Map Spanish field names expected by the frontend to English model fields
    nombre = serializers.CharField(source='name')
    rol = serializers.CharField(source='owner_role', required=False, allow_blank=True, default='')
    empleados = serializers.CharField(source='employees', required=False, allow_blank=True, default='')
    descripcion = serializers.CharField(source='description', required=False, allow_blank=True, default='')

    class Meta:
        model = Organization
        fields = [
            'id', 'nombre', 'rol', 'empleados', 'rut', 'sector', 'descripcion',
            'odoo_url', 'odoo_db', 'odoo_username', 'odoo_connected',
            'created_at',
        ]
        read_only_fields = ['id', 'odoo_connected', 'created_at']

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class OdooIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['odoo_url', 'odoo_db', 'odoo_username', 'odoo_api_key']


class IntegrationScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationScan
        fields = ['id', 'system_name', 'system_type', 'modules_found', 'ai_context', 'recommendations', 'scanned_at']
        read_only_fields = ['id', 'scanned_at']


class ActiveIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActiveIntegration
        fields = ['id', 'integration_type', 'is_active', 'connected_at']
        read_only_fields = ['id', 'connected_at']


class SystemConnectionSerializer(serializers.ModelSerializer):
    connector_type_display = serializers.CharField(source='get_connector_type_display', read_only=True)
    # Único dato de `config` (cifrado, nunca expuesto entero) que el frontend necesita
    # mostrar — el nombre de la carpeta de Drive elegida en el Picker.
    drive_folder_name = serializers.SerializerMethodField()
    # Cuantos archivos trajo esta carpeta. Sirve para no mentir en la interfaz:
    # "sincronizado" con cero documentos es un problema, no un exito.
    drive_documentos = serializers.SerializerMethodField()
    # Que se conecto: el nombre de la carpeta o cuantos archivos se eligieron.
    drive_seleccion = serializers.SerializerMethodField()

    class Meta:
        model = SystemConnection
        fields = [
            'id', 'organization', 'name', 'connector_type', 'connector_type_display',
            'category', 'schema_cache', 'is_active', 'last_synced_at', 'created_at',
            'drive_folder_name', 'drive_documentos', 'drive_seleccion',
        ]
        read_only_fields = ['id', 'schema_cache', 'last_synced_at', 'created_at']

    def get_drive_seleccion(self, obj):
        if obj.connector_type != 'google_drive':
            return None
        cfg = obj.get_config()
        if cfg.get('folder_name'):
            return f"Carpeta: {cfg['folder_name']}"
        elegidos = cfg.get('file_ids') or []
        if len(elegidos) == 1:
            return elegidos[0].get('name') or '1 archivo'
        if elegidos:
            return f'{len(elegidos)} archivos elegidos'
        return None

    def get_drive_documentos(self, obj):
        if obj.connector_type != 'google_drive':
            return None
        from .models import CompanyDocument
        return CompanyDocument.objects.filter(
            organization_id=obj.organization_id, source='drive_sync',
        ).count()

    def get_drive_folder_name(self, obj):
        if obj.connector_type != 'google_drive':
            return None
        return obj.get_config().get('folder_name') or None


class OrganizationContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationContext
        fields = [
            'business_description', 'products_services', 'target_customers',
            'glossary', 'tone_guidelines', 'restrictions', 'updated_at',
        ]
        read_only_fields = ['updated_at']


class CompanyDocumentSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = CompanyDocument
        fields = [
            'id', 'title', 'category', 'category_display', 'file', 'is_public', 'size',
            'is_mine', 'summary', 'processing_error', 'uploaded_by_name', 'created_at',
        ]
        read_only_fields = [
            'id', 'size', 'is_mine', 'summary', 'processing_error', 'uploaded_by_name', 'created_at',
        ]

    def get_size(self, obj):
        try:
            return obj.file.size
        except (ValueError, OSError):
            return 0

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return bool(request and obj.uploaded_by_id == request.user.id)

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return ''
        return obj.uploaded_by.first_name or obj.uploaded_by.email.split('@')[0]


class ContextCubicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContextCubicle
        fields = ['id', 'title', 'content', 'order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
