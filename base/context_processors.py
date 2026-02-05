"""
Context processors para templates globales.
"""
from django.conf import settings


def catering_context(request):
    """Expone el nombre y colores de marca del catering a todas las plantillas."""
    openai_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    return {
        'catering_name': getattr(settings, 'CATERING_NAME', 'Catering'),
        'brand_color': getattr(settings, 'BRAND_COLOR', '#7CB342'),
        'brand_color_hover': getattr(settings, 'BRAND_COLOR_HOVER', '#689F38'),
        'openai_available': bool(openai_key.strip()),
    }
