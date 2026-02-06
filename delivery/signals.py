"""
Señales para reaccionar a cambios en contratos (ej. nuevas coordenadas)
y recalcular el orden de entrega en las rutas afectadas.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from contracts.models import Contrato


@receiver(pre_save, sender=Contrato)
def contrato_store_old_coords(sender, instance, **kwargs):
    """Guarda lat/lng anteriores antes del save para detectar cambios."""
    if instance.pk:
        row = Contrato.objects.filter(pk=instance.pk).values_list('latitud', 'longitud').first()
        instance._old_contrato_lat_lng = (row[0], row[1]) if row else (None, None)
    else:
        instance._old_contrato_lat_lng = (None, None)


@receiver(post_save, sender=Contrato)
def contrato_coords_changed_recalc_routes(sender, instance, created, **kwargs):
    """
    Si un contrato activo recibe nuevas coordenadas (lat/lng), recalcula el orden
    de entrega de todas las rutas presente (día actual) y futuras que incluyan ese contrato.
    """
    from routes.models import Ruta
    from .services.google_maps_ruta import optimizar_orden_entregas

    if created:
        return
    old = getattr(instance, '_old_contrato_lat_lng', None)
    if old is None:
        return
    new = (instance.latitud, instance.longitud)
    if old == new:
        return
    if not instance.esta_activo():
        return
    today = timezone.now().date()
    rutas = Ruta.objects.filter(
        fecha__gte=today,
        ruta_clientes__contrato=instance,
    ).distinct()
    for ruta in rutas:
        optimizar_orden_entregas(ruta, request=None)
