from django.db import models
from django.core.validators import MinValueValidator


class Ingrediente(models.Model):
    """Modelo para gestionar ingredientes utilizados en las recetas"""
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    unidad_medida = models.CharField(
        max_length=50,
        verbose_name="Unidad de medida",
        help_text="Ej: kg, gr, litros, unidades, etc."
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Ingrediente"
        verbose_name_plural = "Ingredientes"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.unidad_medida})"


class Receta(models.Model):
    """Modelo para gestionar recetas del sistema"""
    CATEGORIA_CHOICES = [
        ('desayuno', 'Desayuno'),
        ('almuerzo', 'Almuerzo'),
        ('cena', 'Cena'),
        ('snack', 'Snack'),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        verbose_name="Categoría"
    )
    info_nutricional = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Información nutricional",
        help_text="Información nutricional en formato JSON (calorías, proteínas, carbohidratos, etc.)"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    ingredientes = models.ManyToManyField(
        Ingrediente,
        through='RecetaIngrediente',
        related_name='recetas',
        verbose_name="Ingredientes"
    )

    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.nombre}"


class RecetaIngrediente(models.Model):
    """Modelo intermedio para la relación many-to-many entre Receta e Ingrediente con cantidad"""
    receta = models.ForeignKey(
        Receta,
        on_delete=models.CASCADE,
        related_name='receta_ingredientes',
        verbose_name="Receta"
    )
    ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.CASCADE,
        related_name='ingrediente_recetas',
        verbose_name="Ingrediente"
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Cantidad"
    )
    unidad_medida = models.CharField(
        max_length=50,
        verbose_name="Unidad de medida",
        help_text="Unidad de medida para esta cantidad específica"
    )

    class Meta:
        verbose_name = "Ingrediente de Receta"
        verbose_name_plural = "Ingredientes de Recetas"
        unique_together = ['receta', 'ingrediente']
        ordering = ['receta', 'ingrediente']

    def __str__(self):
        return f"{self.receta.nombre} - {self.ingrediente.nombre}: {self.cantidad} {self.unidad_medida}"
