"""
Middleware de restricción por perfil: Admin (acceso completo), Cocina (kitchen + recipes),
Entregador (solo delivery relacionado con su usuario).
"""
import json

from django.shortcuts import redirect
from django.http import HttpResponseForbidden

from .ai_logging import reset_token_usage, get_token_usage

from .auth_utils import (
    is_admin,
    is_cocina,
    is_entregador,
    user_has_any_profile,
    get_user_home_url,
    COCINA_URL_PREFIXES,
    ENTREGADOR_URL_PREFIXES,
)

class ProfileAccessMiddleware:
    """
    Tras AuthenticationMiddleware. Restringe URLs según perfil:
    - Superuser / is_staff / grupo Admin: acceso completo.
    - Cocina: solo /kitchen/, /recipes/, /accounts/, static, media.
    - Entregador: solo /delivery/ y /accounts/ (vistas filtran por entregador).
    - Usuario sin ningún perfil: solo /accounts/logout y /accounts/sin-acceso/ (ni dashboard).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if is_admin(request.user):
            return self.get_response(request)

        path = request.path
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # Usuario sin ningún perfil: solo puede ver "sin acceso" y cerrar sesión
        if not user_has_any_profile(request.user):
            if path.rstrip('/').startswith('/accounts/sin-acceso') or path.startswith('/accounts/logout'):
                return self.get_response(request)
            from django.urls import reverse
            return redirect(reverse('sin_acceso'))

        if is_cocina(request.user):
            if any(path.startswith(prefix) for prefix in COCINA_URL_PREFIXES):
                return self.get_response(request)
            return redirect(get_user_home_url(request.user))

        if is_entregador(request.user):
            if any(path.startswith(prefix) for prefix in ENTREGADOR_URL_PREFIXES):
                return self.get_response(request)
            return redirect(get_user_home_url(request.user))

        return self.get_response(request)


class AITokenUsageMiddleware:
    """
    Muestra al usuario cuántos tokens consumió la IA en cada interacción.

    - Reinicia el acumulador de tokens al inicio de cada petición.
    - Si durante la petición hubo llamadas a la IA:
        * Respuestas JSON (acciones AJAX): añade la clave "tokens_ia" al cuerpo.
        * Otras respuestas (HTML / redirect, p. ej. importar receta): guarda el
          consumo como "flash" en la sesión para mostrarlo en la próxima página.
    El front-end (base.html) muestra un aviso flotante con esta información.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reset_token_usage()
        response = self.get_response(request)

        try:
            usage = get_token_usage()
            if not usage or usage.get('total_tokens', 0) <= 0:
                return response

            tokens = {
                'prompt': usage.get('prompt_tokens', 0),
                'completion': usage.get('completion_tokens', 0),
                'total': usage.get('total_tokens', 0),
                'llamadas': usage.get('llamadas', 0),
            }

            content_type = (response.get('Content-Type', '') or '').lower()
            es_json = 'application/json' in content_type and hasattr(response, 'content') and not getattr(response, 'streaming', False)

            if es_json:
                data = json.loads(response.content.decode('utf-8'))
                if isinstance(data, dict):
                    data['tokens_ia'] = tokens
                    response.content = json.dumps(data).encode('utf-8')
                    if response.has_header('Content-Length'):
                        response['Content-Length'] = str(len(response.content))
            elif hasattr(request, 'session'):
                # Flujo HTML/redirect: mostrar en la próxima carga de página.
                request.session['tokens_ia_flash'] = tokens
        except Exception:
            pass

        return response
