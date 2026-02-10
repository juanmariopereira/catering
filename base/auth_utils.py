"""
Utilidades de autenticación y perfiles (grupos): Admin, Cocina, Entregador.
"""
from django.utils import timezone
from django.urls import reverse


# Nombres de grupos (perfiles)
GROUP_ADMIN = 'Admin'
GROUP_COCINA = 'Cocina'
GROUP_ENTREGADOR = 'Entregador'

# Prefijos de URL permitidos por perfil (sin admin)
COCINA_URL_PREFIXES = ('/kitchen/', '/recipes/', '/accounts/')
ENTREGADOR_URL_PREFIXES = ('/delivery/', '/accounts/')


def user_in_group(user, group_name):
    """Indica si el usuario pertenece al grupo dado."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


def user_has_any_profile(user):
    """
    True si el usuario tiene permiso para usar la aplicación: superuser, is_staff
    o pertenece a algún grupo de perfil (Admin, Cocina, Entregador).
    Por defecto, sin perfil no tiene acceso a nada (ni al dashboard).
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return True
    return (
        user_in_group(user, GROUP_ADMIN)
        or user_in_group(user, GROUP_COCINA)
        or user_in_group(user, GROUP_ENTREGADOR)
    )


def is_admin(user):
    """Usuario con acceso completo: is_superuser, is_staff o pertenece al grupo Admin."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'is_superuser', False) or user.is_staff or user_in_group(user, GROUP_ADMIN)


def is_cocina(user):
    """Usuario con perfil Cocina (solo cocina y recetas)."""
    return user_in_group(user, GROUP_COCINA)


def is_entregador(user):
    """Usuario con perfil Entregador (solo sus entregas)."""
    return user_in_group(user, GROUP_ENTREGADOR)


def get_entregador_for_user(user):
    """Devuelve el Entregador asociado al usuario (entregador_perfil) o None."""
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'entregador_perfil', None)


def user_can_access_entregador(user, entregador_id):
    """
    True si el usuario puede acceder a la información del entregador con ese id.
    Admin: siempre. Entregador: solo si entregador_id es su entregador_perfil.
    """
    if is_admin(user):
        return True
    if not is_entregador(user):
        return True  # Otros perfiles sin restricción por entregador
    ep = get_entregador_for_user(user)
    return ep is not None and ep.pk == entregador_id


def get_user_home_url(user):
    """
    URL de inicio según perfil (fuera del admin).
    - Admin / staff / superuser: dashboard
    - Cocina: /kitchen/
    - Entregador: /delivery/ruta/<fecha_actual>/<entregador_id>/
    - Sin perfil: página "sin acceso"
    """
    if not user or not user.is_authenticated:
        return reverse('login')

    if not user_has_any_profile(user):
        return reverse('sin_acceso')

    if is_cocina(user) and not is_admin(user):
        return '/kitchen/'

    if is_entregador(user) and not is_admin(user):
        entregador = get_entregador_for_user(user)
        if entregador:
            hoy = timezone.now().date().isoformat()
            return reverse(
                'delivery:ruta_fecha_entregador',
                kwargs={'fecha_str': hoy, 'entregador_id': entregador.pk},
            )
        return reverse('sin_acceso')

    return reverse('dashboard')


class RequireProfileMixin:
    """
    Mixin para vistas: solo permite acceso si el usuario tiene uno de los perfiles indicados.
    Por defecto solo Admin. Sobrescribe dispatch para redirigir a la home del usuario si no tiene permiso.
    """
    allowed_profiles = None  # ej: ['Admin'] o ['Admin', 'Cocina']

    def get_allowed_profiles(self):
        if self.allowed_profiles is None:
            return [GROUP_ADMIN]
        return list(self.allowed_profiles)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        allowed = self.get_allowed_profiles()
        if GROUP_ADMIN in allowed and is_admin(request.user):
            return super().dispatch(request, *args, **kwargs)
        if GROUP_COCINA in allowed and is_cocina(request.user):
            return super().dispatch(request, *args, **kwargs)
        if GROUP_ENTREGADOR in allowed and is_entregador(request.user):
            return super().dispatch(request, *args, **kwargs)
        from django.shortcuts import redirect
        return redirect(get_user_home_url(request.user))
