"""
Señales para reaccionar a cambios en contratos (ej. nuevas coordenadas)
y recalcular el orden de entrega en las rutas afectadas.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
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
    Antes recalculaba el orden de entrega al cambiar coordenadas del contrato.
    Ahora el orden se calcula solo bajo demanda (botón "Calcular orden óptimo" en la ruta).
    Se mantiene el receptor para no romper imports; no hace nada.
    """
    pass
