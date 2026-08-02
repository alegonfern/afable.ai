from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, RegisterView,
    PasswordResetRequestView, PasswordResetConfirmView,
    GoogleLoginStartView, GoogleLoginCallbackView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('google/login/', GoogleLoginStartView.as_view(), name='auth-google-login'),
    path('google/callback/', GoogleLoginCallbackView.as_view(), name='auth-google-callback'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
