"""
Configuración para entorno de producción.
Carga variables desde .env.production y define DEBUG=False, BD desde env, etc.

Uso: export DJANGO_SETTINGS_MODULE=base.settings.production
"""
import os
from pathlib import Path

# Cargar .env.production antes de importar base (proyecto raíz = parent de base)
_project_root = Path(__file__).resolve().parent.parent.parent
_env_production = _project_root / '.env.production'
if _env_production.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_production)

from .base import *

DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY and not DEBUG:
    raise ValueError('SECRET_KEY debe estar definido en producción (ej. en .env.production).')

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()
]
if not ALLOWED_HOSTS and not DEBUG:
    raise ValueError('ALLOWED_HOSTS debe estar definido en producción (dominios separados por coma).')

# Base de datos desde variables de entorno
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'catering'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Static y media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Seguridad: cookies solo por HTTPS
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()
]

# HSTS (opcional)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Marca / nombre del catering (opcional desde env)
if os.environ.get('CATERING_NAME'):
    CATERING_NAME = os.environ.get('CATERING_NAME')
if os.environ.get('BRAND_COLOR'):
    BRAND_COLOR = os.environ.get('BRAND_COLOR')
if os.environ.get('BRAND_COLOR_HOVER'):
    BRAND_COLOR_HOVER = os.environ.get('BRAND_COLOR_HOVER')

# Email: en producción usar backend real (SMTP, etc.)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)

# Cache: en producción usar Redis o Memcached si está disponible
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Logging: a archivo y nivel INFO
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# No permitir cargar datos de prueba en producción
ALLOW_LOAD_TEST_DATA = False
