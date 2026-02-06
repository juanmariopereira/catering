from django.db import models
from django.core.validators import MinValueValidator


class TipoReceta(models.Model):
    """
    Tipo de receta parametrizable: Comida, Masa, Postre, Complemento, Bebida, Fruta, etc.
    """
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre")
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden para mostrar en listas"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Tipo de receta"
        verbose_name_plural = "Tipos de receta"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Alergeno(models.Model):
    """
    Catálogo de alérgenos predefinidos (gluten, lactosa, frutos secos, etc.).
    Se usa en ingredientes para elegir de una lista en lugar de texto libre.
    """
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre")
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden para mostrar en listas"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Alérgeno"
        verbose_name_plural = "Alérgenos"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class UnidadMedida(models.Model):
    """Unidad de medida parametrizable: kg, gr, lt, un, etc."""
    TIPO_PESO = 'peso'
    TIPO_VOLUMEN = 'volumen'
    TIPO_UNIDAD = 'unidad'
    TIPO_CHOICES = [
        (TIPO_PESO, 'Peso'),
        (TIPO_VOLUMEN, 'Volumen'),
        (TIPO_UNIDAD, 'Unidad'),
    ]
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre")
    simbolo = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Símbolo",
        help_text="Opcional: ej. kg, g, L"
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default=TIPO_PESO,
        verbose_name="Tipo",
        help_text="Peso (g, kg), Volumen (ml, L) o Unidad (piezas). En la receta solo se pueden elegir unidades del mismo tipo que el ingrediente."
    )
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden para mostrar en listas"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Unidad de medida"
        verbose_name_plural = "Unidades de medida"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.simbolo or self.nombre


class TipoIngrediente(models.Model):
    """
    Tipo de ingrediente: Lácteos, Granos, Cereales, Legumbres, Carnes, Aceites,
    Salsas, Hortalizas, Sazonadores, Frutas, Pescados y mariscos, etc.
    """
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre")
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden",
        help_text="Orden para mostrar en listas"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Tipo de ingrediente"
        verbose_name_plural = "Tipos de ingrediente"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Ingrediente(models.Model):
    """Modelo para gestionar ingredientes utilizados en las recetas"""
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    tipo_ingrediente = models.ForeignKey(
        TipoIngrediente,
        on_delete=models.PROTECT,
        related_name='ingredientes',
        verbose_name="Tipo de ingrediente",
        blank=True,
        null=True,
        help_text="Categoría del ingrediente: lácteos, hortalizas, carnes, etc."
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        related_name='ingredientes',
        verbose_name="Unidad de medida",
        help_text="Unidad por defecto para este ingrediente",
        blank=True,
        null=True,
    )
    equivalencia_por_unidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Equivalencia por unidad",
        help_text="Cuando la unidad es 'Unidad', indique cuántos gramos o ml tiene cada unidad (ej. 1 huevo = 50 g)."
    )
    equivalencia_por_unidad_tipo = models.CharField(
        max_length=5,
        choices=[('g', 'Gramos'), ('ml', 'Mililitros')],
        blank=True,
        default='g',
        verbose_name="Tipo de equivalencia",
        help_text="Si la equivalencia anterior es en gramos o en mililitros."
    )
    info_nutricional = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Información nutricional",
        help_text="Por 100g en formato JSON: {\"por_100g\": {\"calorias\": 165, \"proteinas\": 31, \"carbohidratos\": 0, \"grasas\": 3.6, \"fibra\": 0}}. Opcional: \"gramos_por_unidad\" para ingredientes vendidos por unidad."
    )
    alergenos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Alérgenos",
        help_text="Lista de alérgenos que puede contener (gluten, lactosa, frutos secos, etc.)"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Ingrediente"
        verbose_name_plural = "Ingredientes"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre}"


class Receta(models.Model):
    """Modelo para gestionar recetas del sistema"""

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    tipos_receta = models.ManyToManyField(
        TipoReceta,
        related_name='recetas',
        blank=True,
        verbose_name="Tipo de receta",
        help_text="Ej: Comida, Masa, Postre, Complemento, Bebida, Fruta (selección múltiple)"
    )
    momentos_dia = models.ManyToManyField(
        'diets.TipoComida',
        related_name='recetas_momento',
        blank=True,
        verbose_name="Momentos del día",
        help_text="En qué momentos del día se puede usar esta receta: Desayuno, Media mañana, Comida, Merienda, Cena (selección múltiple)"
    )
    info_nutricional = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Información nutricional",
        help_text="Información nutricional en formato JSON (calorías, proteínas, carbohidratos, etc.)"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    producido_en_cocina = models.BooleanField(
        default=True,
        verbose_name="Es producido en cocina",
        help_text="Si está marcado, la receta se incluye en el Resumen — Cantidades por comida del detalle de cocina."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    ingredientes = models.ManyToManyField(
        Ingrediente,
        through='RecetaIngrediente',
        related_name='recetas',
        verbose_name="Ingredientes",
        help_text="Ingredientes y cantidades (selección múltiple con cantidad y unidad)"
    )

    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        ordering = ['nombre']

    def __str__(self):
        tipos = ", ".join(t.nombre for t in self.tipos_receta.all()[:3])
        return f"{self.nombre}" + (f" ({tipos})" if tipos else "")


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
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        related_name='receta_ingredientes',
        verbose_name="Unidad de medida",
        help_text="Unidad para esta cantidad en la receta",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Ingrediente de Receta"
        verbose_name_plural = "Ingredientes de Recetas"
        unique_together = ['receta', 'ingrediente']
        ordering = ['receta', 'ingrediente']

    def __str__(self):
        um = getattr(self.unidad_medida, 'nombre', None) or getattr(self.unidad_medida, 'simbolo', None) or '—'
        return f"{self.receta.nombre} - {self.ingrediente.nombre}: {self.cantidad} {um}"
