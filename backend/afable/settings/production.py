from .base import *

DEBUG = False

# El front (CRA) ya ocupa /static/ servido por nginx; los estáticos de Django
# (admin, DRF browsable API) van en una ruta propia para no chocar.
STATIC_URL = '/django-static/'

# nginx termina el SSL y reenvía por http al gunicorn local; que Django sepa
# que la conexión original es https (cookies seguras, redirects, etc.)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://getafable.com,https://www.getafable.com',
).split(',')
