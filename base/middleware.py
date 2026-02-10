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
    get_user_home_url,
    COCINA_URL_PREFIXES,
    ENTREGADOR_URL_PREFIXES,
)


class ProfileAccessMiddleware:
    """
    Tras AuthenticationMiddleware. Restringe URLs según perfil:
    - Admin / is_staff: acceso completo (y al admin de Django).
    - Cocina: solo /kitchen/, /recipes/, /accounts/, static, media.
    - Entregador: solo /delivery/ y /accounts/ (las vistas de delivery filtran por entregador en auth_utils).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if is_admin(request.user):
            return self.get_response(request)

        path = request.path
        # Static/media y admin siempre permitidos por configuración; admin requiere is_staff
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        if is_cocina(request.user):
            if any(path.startswith(prefix) for prefix in COCINA_URL_PREFIXES):
                return self.get_response(request)
            return redirect(get_user_home_url(request.user))

        if is_entregador(request.user):
            if any(path.startswith(prefix) for prefix in ENTREGADOR_URL_PREFIXES):
                return self.get_response(request)
            return redirect(get_user_home_url(request.user))

        # Usuario sin perfil asignado: permitir dashboard y accounts
        if path.startswith('/dashboard/') or path.startswith('/accounts/'):
            return self.get_response(request)
        if path == '/' or path == '/dashboard/':
            return self.get_response(request)

        return self.get_response(request)
