from django.db import models
from django.core.validators import MinValueValidator


class DetalleCocina(models.Model):
    """
    Modelo para gestionar detalles de platos a elaborar por fecha.
    Este modelo agrupa las planificaciones por fecha mostrando recetas a preparar.
    """
    fecha = models.DateField(verbose_name="Fecha", unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas para el cocinero")

    class Meta:
        verbose_name = "Detalle de Cocina"
        verbose_name_plural = "Detalles de Cocina"
        ordering = ['-fecha']

    def __str__(self):
        return f"Detalle Cocina - {self.fecha}"

    @classmethod
    def obtener_recetas_por_fecha(cls, fecha):
        """
        Obtiene todas las recetas a preparar para una fecha específica,
        agrupadas por receta con la cantidad total.
        Usa PlanificacionMenu (fecha + plan) y PlanificacionClienteSustituta.
        """
        from planning.utils import recetas_a_preparar_por_fecha
        return recetas_a_preparar_por_fecha(fecha)
