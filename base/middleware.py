"""
Middleware de restricción por perfil: Admin (acceso completo), Cocina (kitchen + recipes),
Entregador (solo delivery relacionado con su usuario).
"""
from django.shortcuts import redirect
from django.http import HttpResponseForbidden

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
