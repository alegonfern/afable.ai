from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'apps.authentication',
    # Workspaces: pertenencia, roles e invitaciones. Es la fuente de verdad de los
    # permisos (apps/workspaces/permissions.py) y reemplaza a User.org_admin/areas.
    'apps.workspaces',
    # La app que ya existia, que se va reemplazando pantalla por pantalla.
    'apps.organizations',
    'apps.agents',
    # Fuentes de conocimiento: el corpus troceado y vectorizado (busqueda semantica).
    'apps.sources',
    # Sesiones: donde se trabaja en equipo — conversaciones, tareas y archivos.
    # El cascaron se llamaba `rooms` (por "Salas"); se renombro al concepto real.
    'apps.sesiones',
    # Todavia vacia.
    'apps.tools',
    'apps.payments',
    'apps.leads',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'afable.urls'
AUTH_USER_MODEL = 'authentication.User'
WSGI_APPLICATION = 'afable.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='afable'),
        'USER': config('DB_USER', default='afable'),
        'PASSWORD': config('DB_PASSWORD', default='afable'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Solo aplica a vistas que declaran throttle_scope (p. ej. el chat público de leads).
    'DEFAULT_THROTTLE_RATES': {
        'lead_chat': '20/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

AFABLE_TEAM_EMAIL = config('AFABLE_TEAM_EMAIL', default='alegonfern@gmail.com')

ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
DEEPSEEK_API_KEY = config('DEEPSEEK_API_KEY', default='')
DEEPSEEK_MODEL = config('DEEPSEEK_MODEL', default='deepseek-v4-flash')

# Correo (automatizaciones/rutinas). Sin EMAIL_HOST_USER el backend es consola:
# el correo se imprime en los logs — útil en desarrollo.
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'afable@localhost')
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST_USER
    else 'django.core.mail.backends.console.EmailBackend'
)

# Flow Payments
FLOW_API_KEY = config('FLOW_API_KEY', default='')
FLOW_SECRET_KEY = config('FLOW_SECRET_KEY', default='')
FLOW_SANDBOX = config('FLOW_SANDBOX', default=True, cast=bool)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3001')
BACKEND_URL = config('BACKEND_URL', default='http://localhost:8001')

# Google OAuth — compartido entre "Iniciar sesión con Google" y la sincronización
# de una carpeta de Drive (mismo proyecto/credenciales de Google Cloud, dos scopes).
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
FLOW_WEBHOOK_URL = config('FLOW_WEBHOOK_URL', default='http://localhost:8001/api/v1/payments/webhook/confirm/')
FLOW_RETURN_URL  = config('FLOW_RETURN_URL',  default='http://localhost:8001/api/v1/payments/return/')

# AI provider: 'anthropic' | 'ollama' (local) | 'ollama_cloud' (Ollama Cloud)
AI_PROVIDER    = config('AI_PROVIDER', default='ollama')
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434')
OLLAMA_MODEL   = config('OLLAMA_MODEL', default='qwen2.5:7b')

# Ollama Cloud: modelos grandes alojados por Ollama, misma API nativa /api/chat.
# La key se lee del entorno y nunca se hardcodea. gpt-oss:120b es del tier gratuito.
OLLAMA_API_KEY        = config('OLLAMA_API_KEY', default='')
OLLAMA_CLOUD_BASE_URL = config('OLLAMA_CLOUD_BASE_URL', default='https://ollama.com')
OLLAMA_CLOUD_MODEL    = config('OLLAMA_CLOUD_MODEL', default='gpt-oss:120b')
# Modelos cloud a exponer en el selector de la app aunque no aparezcan en /api/tags
# (lista separada por comas, ej: "gpt-oss:120b-cloud,qwen3-coder:480b-cloud").
OLLAMA_CLOUD_MODELS   = [m.strip() for m in config('OLLAMA_CLOUD_MODELS', default='').split(',') if m.strip()]

# Busqueda semantica (Knowledge > Search). Proveedor de embeddings: 'ollama' o
# 'ninguno' para apagarla (los documentos vuelven a volcarse enteros al prompt,
# como antes de que existiera). Anthropic no tiene API de embeddings, asi que la
# ANTHROPIC_API_KEY no sirve aca.
#
# OJO: el modelo define la dimension del vector, y la dimension esta en la
# migracion de `apps.sources.Fragmento` (768 = embeddinggemma). Cambiar a un
# modelo de otra dimension exige una migracion nueva y reindexar todo.
EMBEDDINGS_PROVIDER = config('EMBEDDINGS_PROVIDER', default='ollama')
EMBEDDINGS_MODEL    = config('EMBEDDINGS_MODEL', default='embeddinggemma')
# Vacio = usar OLLAMA_BASE_URL. Se separa para poder tener el modelo de embeddings
# en otra maquina que el de chat.
EMBEDDINGS_BASE_URL = config('EMBEDDINGS_BASE_URL', default='')
