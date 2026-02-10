"""
Permissions for deliveries API: only couriers (users with CourierProfile) can access.
"""
from rest_framework import permissions


class IsCourier(permissions.BasePermission):
    """
    Only users with a CourierProfile (linked to an Entregador) can access.
    """
    message = 'You must be a courier to access this resource.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        from .models import CourierProfile
        return CourierProfile.objects.filter(user=request.user).exists()
