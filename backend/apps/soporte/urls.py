from django.urls import path

from .views import MensajeSoporteView

urlpatterns = [
    path('', MensajeSoporteView.as_view(), name='soporte-mensaje'),
]
