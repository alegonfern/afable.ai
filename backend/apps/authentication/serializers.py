from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, UserContext


class UserContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserContext
        fields = ['about_me', 'priorities', 'custom_instructions', 'updated_at']
        read_only_fields = ['updated_at']


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Credenciales incorrectas.')
        if not user.is_active:
            raise serializers.ValidationError('Cuenta desactivada.')
        data['user'] = user
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Lo mínimo para entrar, más el nombre de la empresa.

    ⭐ **El nombre de la empresa se pregunta acá y no después.** Sin él, toda empresa nacía
    llamándose "Empresa de Pedro": el primer nombre que ve quien se registra —y el que ven
    después sus colegas— es uno inventado por nosotros. En un producto que se vende como
    "IA para equipos", empezar con el nombre del equipo mal puesto no es un detalle.

    Es opcional: quien no lo escriba entra igual y lo cambia en Administración. Poner una
    pared en el registro cuesta más de lo que vale el dato.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    empresa = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=200,
    )

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'empresa']

    def create(self, validated_data):
        # `empresa` no es del modelo User: se saca antes de crearlo y la vista la usa para
        # nombrar la Organization.
        validated_data.pop('empresa', None)
        return User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'avatar_url',
            'role', 'department', 'objectives', 'response_style', 'date_joined',
        ]
        read_only_fields = ['id', 'email', 'date_joined']

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return obj.google_avatar_url or None


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Contraseña actual incorrecta.')
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8)
