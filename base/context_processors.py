"""
Context processors para templates globales.
"""
from django.conf import settings
from django.utils import timezone

from .auth_utils import is_admin, is_cocina, is_entregador, get_user_home_url


def catering_context(request):
    """Expone el nombre, colores de marca y logo del catering a todas las plantillas."""
    from base.models import ParametroSistema

    from base.ai_provider import ia_disponible

    maps_key = getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', '') or ''
    param_logo = ParametroSistema.objects.filter(clave='logo_empresa').first()
    path_logo = (param_logo.valor or '').strip() if param_logo else ''
    if path_logo:
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        if media_url and not media_url.startswith('/'):
            media_url = '/' + media_url
        logo_empresa_url = (media_url.rstrip('/') + '/' + path_logo.replace('\\', '/'))
    else:
        logo_empresa_url = ''

    ctx = {
        'catering_name': getattr(settings, 'CATERING_NAME', 'Catering'),
        'brand_color': getattr(settings, 'BRAND_COLOR', '#7CB342'),
        'brand_color_hover': getattr(settings, 'BRAND_COLOR_HOVER', '#689F38'),
        'logo_empresa_url': logo_empresa_url,
        'openai_available': ia_disponible(),
        'google_maps_browser_key': maps_key,
    }
    # Perfiles para menú y redirección (Admin, Cocina, Entregador)
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        ctx['is_admin_profile'] = is_admin(user)
        ctx['is_cocina_profile'] = is_cocina(user) and not is_admin(user)
        ctx['is_entregador_profile'] = is_entregador(user) and not is_admin(user)
        ctx['user_home_url'] = get_user_home_url(user)
    else:
        ctx['is_admin_profile'] = False
        ctx['is_cocina_profile'] = False
        ctx['is_entregador_profile'] = False
        ctx['user_home_url'] = None
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
    # Consumo de tokens de IA de la petición anterior (flujos HTML/redirect).
    # Se extrae (pop) para mostrarlo una sola vez.
    session = getattr(request, 'session', None)
    ctx['tokens_ia_flash'] = session.pop('tokens_ia_flash', None) if session is not None else None
    return ctx