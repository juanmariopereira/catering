"""
Context processors para templates globales.
"""
from django.conf import settings
from django.utils import timezone


def catering_context(request):
    """Expone el nombre y colores de marca del catering a todas las plantillas."""
    openai_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    ctx = {
        'catering_name': getattr(settings, 'CATERING_NAME', 'Catering'),
        'brand_color': getattr(settings, 'BRAND_COLOR', '#7CB342'),
        'brand_color_hover': getattr(settings, 'BRAND_COLOR_HOVER', '#689F38'),
        'openai_available': bool(openai_key.strip()),
    }
    # Contratos vigentes con entrega hoy que no están en ninguna ruta (para banner global)
    if getattr(request, 'user', None) and request.user.is_authenticated:
        try:
            from delivery.utils import contratos_sin_ruta_en_fecha
            hoy = timezone.now().date()
            ctx['contratos_sin_ruta_hoy_count'] = contratos_sin_ruta_en_fecha(hoy).count()
            ctx['contratos_sin_ruta_hoy_fecha'] = hoy
        except Exception:
            ctx['contratos_sin_ruta_hoy_count'] = 0
            ctx['contratos_sin_ruta_hoy_fecha'] = None
    else:
        ctx['contratos_sin_ruta_hoy_count'] = 0
        ctx['contratos_sin_ruta_hoy_fecha'] = None
    return ctx
