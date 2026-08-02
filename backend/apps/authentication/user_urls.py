from django.urls import path
from .views import (
    MeView, ChangePasswordView, AvatarView, AvatarDeleteView, MyContextView,
)

urlpatterns = [
    path('me/', MeView.as_view(), name='user-me'),
    path('me/context/', MyContextView.as_view(), name='user-context'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('avatar/', AvatarView.as_view(), name='user-avatar'),
    path('avatar/delete/', AvatarDeleteView.as_view(), name='user-avatar-delete'),
]
