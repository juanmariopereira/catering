"""
Settings module - carga la configuración según el entorno
"""
import os

# Determinar qué configuración usar según la variable de entorno
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development')

if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'staging':
    from .staging import *
else:
    # Por defecto, usar development
    from .development import *
