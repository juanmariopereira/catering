from django.db import models
from django.core.validators import MinValueValidator


class TipoComida(models.Model):
    """
    Momento del día en que se consume una comida (desayuno, media mañana, comida, etc.).
    Cada merienda/comida puede tener varias recetas (ej. media mañana = té + galleta + cereal).
    """
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre")
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden del momento en el día (1 = desayuno, 2 = media mañana, ...)"
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Descripción"
    )

    class Meta:
        verbose_name = "Tipo de comida / Momento"
        verbose_name_plural = "Tipos de comida / Momentos"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Dieta(models.Model):
    """Modelo para gestionar dietas (conjuntos de recetas). Una dieta puede asociarse a varios planes."""
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    planes = models.ManyToManyField(
        'plans.Plan',
        related_name='dietas',
        blank=True,
        verbose_name="Planes asociados",
        help_text="Planes para los que puede usarse esta dieta (ej. Calórico, Adelgazamiento)"
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
    """
    Receta asignada a una dieta en un momento del día (comida).
    Cada momento puede tener varias recetas (ej. media mañana = té + galleta + cereal).
    """
    dieta = models.ForeignKey(
        Dieta,
        on_delete=models.CASCADE,
        related_name='dieta_recetas',
        verbose_name="Dieta"
    )
    tipo_comida = models.ForeignKey(
        TipoComida,
        on_delete=models.PROTECT,
        related_name='dieta_recetas',
        verbose_name="Momento / Tipo de comida",
        blank=True,
        null=True,
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
        help_text="Orden de la receta dentro de ese momento (ej. 1º té, 2º galleta, 3º cereal)"
    )

    class Meta:
        verbose_name = "Receta de Dieta"
        verbose_name_plural = "Recetas de Dietas"
        unique_together = ['dieta', 'tipo_comida', 'receta']
        ordering = ['dieta', 'tipo_comida', 'orden', 'receta']

    def __str__(self):
        tipo = getattr(self.tipo_comida, 'nombre', None) or '—'
        return f"{self.dieta.nombre} - {tipo}: {self.receta.nombre} (#{self.orden})"
