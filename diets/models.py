from django.db import models
from django.core.validators import MinValueValidator


class Dieta(models.Model):
    """Modelo para gestionar dietas (conjuntos de recetas)"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    plan = models.ForeignKey(
        'plans.Plan',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='dietas',
        verbose_name="Plan asociado"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    recetas = models.ManyToManyField(
        'recipes.Receta',
        through='DietaReceta',
        related_name='dietas',
        verbose_name="Recetas"
    )

    class Meta:
        verbose_name = "Dieta"
        verbose_name_plural = "Dietas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class DietaReceta(models.Model):
    """Modelo intermedio para la relación many-to-many entre Dieta y Receta con orden"""
    dieta = models.ForeignKey(
        Dieta,
        on_delete=models.CASCADE,
        related_name='dieta_recetas',
        verbose_name="Dieta"
    )
    receta = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.CASCADE,
        related_name='receta_dietas',
        verbose_name="Receta"
    )
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden de la receta en la dieta (para secuencia de días)"
    )

    class Meta:
        verbose_name = "Receta de Dieta"
        verbose_name_plural = "Recetas de Dietas"
        unique_together = ['dieta', 'receta']
        ordering = ['dieta', 'orden', 'receta']

    def __str__(self):
        return f"{self.dieta.nombre} - {self.receta.nombre} (Orden: {self.orden})"
