from django.db import models
from django.core.validators import MinValueValidator


class Plan(models.Model):
    """Modelo para gestionar planes de catering"""
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del plan")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio base"
    )
    caracteristicas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Características",
        help_text="Características del plan en formato JSON"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
