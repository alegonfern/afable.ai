from urllib.parse import urlencode
import requests as http_requests
from django.conf import settings
from django.shortcuts import redirect
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, PasswordResetToken, UserContext
from apps.organizations.models import Organization
from .serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, UserContextSerializer,
)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response(_tokens_for_user(user), status=status.HTTP_200_OK)


_GOOGLE_LOGIN_SCOPE = 'openid email profile'


def _google_login_redirect_uri():
    return f'{settings.BACKEND_URL}/api/v1/auth/google/callback/'


class GoogleLoginStartView(APIView):
    """Arranca el login con Google — mismo proyecto/credenciales de Google Cloud
    que usa la sincronización de Drive, pero con scope liviano (solo identidad)."""
    permission_classes = [AllowAny]

    def get(self, request):
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': _google_login_redirect_uri(),
            'response_type': 'code',
            'scope': _GOOGLE_LOGIN_SCOPE,
            'access_type': 'online',
            'prompt': 'select_account',
        }
        return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}')


class GoogleLoginCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        if not code:
            return redirect(f'{settings.FRONTEND_URL}/login?error=google_denied')

        token_resp = http_requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': _google_login_redirect_uri(),
            'grant_type': 'authorization_code',
        })
        if token_resp.status_code != 200:
            return redirect(f'{settings.FRONTEND_URL}/login?error=google_token')

        try:
            claims = google_id_token.verify_oauth2_token(
                token_resp.json()['id_token'], google_auth_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return redirect(f'{settings.FRONTEND_URL}/login?error=google_invalid')

        email = claims.get('email')
        if not email:
            return redirect(f'{settings.FRONTEND_URL}/login?error=google_no_email')

        user, created = User.objects.get_or_create(email=email, defaults={
            'username': email,
            'first_name': claims.get('given_name', ''),
            'last_name': claims.get('family_name', ''),
        })
        if created:
            user.set_unusable_password()

        picture = claims.get('picture', '')
        if picture and picture != user.google_avatar_url:
            user.google_avatar_url = picture
        if created or picture:
            user.save()

        if created:
            Organization.crear_para_dueno(user)

        jwt_tokens = _tokens_for_user(user)
        callback_url = f"{settings.FRONTEND_URL}/auth/google/callback#access={jwt_tokens['access']}&refresh={jwt_tokens['refresh']}"
        return redirect(callback_url)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        Organization.crear_para_dueno(
            user, name=(serializer.validated_data.get('empresa') or '').strip() or None,
        )
        return Response(_tokens_for_user(user), status=status.HTTP_201_CREATED)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            token = PasswordResetToken.create_for_user(user)
            return Response({'detail': 'Correo enviado.', 'token': token.token})
        except User.DoesNotExist:
            return Response({'detail': 'Correo enviado.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data['token']
        new_password = serializer.validated_data['password']

        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(token=token_str)
        except PasswordResetToken.DoesNotExist:
            return Response({'detail': 'Token inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        if not reset_token.is_valid():
            return Response({'detail': 'Token expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        reset_token.user.set_password(new_password)
        reset_token.user.save()
        reset_token.used = True
        reset_token.save()

        return Response({'detail': 'Contraseña actualizada.'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MyContextView(APIView):
    """Capa personal de "Mi contexto" — cada usuario edita solo la suya."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ctx, _ = UserContext.objects.get_or_create(user=request.user)
        return Response(UserContextSerializer(ctx).data)

    def patch(self, request):
        ctx, _ = UserContext.objects.get_or_create(user=request.user)
        serializer = UserContextSerializer(ctx, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'detail': 'Contraseña actualizada.'})


class AvatarView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('avatar')
        if not file:
            return Response({'detail': 'No se envió imagen.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = file
        user.save()
        return Response(UserSerializer(user, context={'request': request}).data)


class AvatarDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
