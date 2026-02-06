from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator


class PlanificacionMenu(models.Model):
    """
    Planificación por fecha y plan: define el menú (comidas por momento del día)
    para un plan en una fecha. Frutas, postres y bebidas se definen por momento
    (Desayuno, Media mañana, Comida, Merienda, Cena) en PlanificacionMenuReceta.
    """
    fecha = models.DateField(verbose_name="Fecha")
    plan = models.ForeignKey(
        'plans.Plan',
        on_delete=models.CASCADE,
        related_name='planificaciones_menu',
        verbose_name="Plan"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas")

    class Meta:
        verbose_name = "Planificación menú (fecha + plan)"
        verbose_name_plural = "Planificaciones menú"
        unique_together = ['fecha', 'plan']
        ordering = ['-fecha', 'plan']

    def __str__(self):
        return f"{self.fecha} - {self.plan.nombre}"


class PlanificacionMenuReceta(models.Model):
    """
    Receta (comida, bebida, fruta, postre) asignada a un momento del día
    dentro de un menú planificado (fecha + plan).
    """
    planificacion_menu = models.ForeignKey(
        PlanificacionMenu,
        on_delete=models.CASCADE,
        related_name='recetas',
        verbose_name="Planificación menú"
    )
    tipo_comida = models.ForeignKey(
        'diets.TipoComida',
        on_delete=models.PROTECT,
        related_name='planificaciones_menu_receta',
        verbose_name="Momento del día"
    )
    receta = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.PROTECT,
        related_name='planificaciones_menu_receta',
        verbose_name="Receta"
    )
    orden = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Orden"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Receta del menú planificado"
        verbose_name_plural = "Recetas del menú planificado"
        unique_together = ['planificacion_menu', 'tipo_comida', 'receta']
        ordering = ['planificacion_menu', 'tipo_comida', 'orden']

    def __str__(self):
        return f"{self.planificacion_menu} - {self.tipo_comida.nombre}: {self.receta.nombre}"


class PlanificacionClienteSustituta(models.Model):
    """
    Sustitución individualizada: para un cliente (contrato) en una fecha,
    en un momento del día, se sirve receta_sustituta en lugar de receta_original
    (ej. por ingredientes que no le gustan).
    """
    fecha = models.DateField(verbose_name="Fecha")
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='sustituciones_planificacion',
        verbose_name="Contrato"
    )
    tipo_comida = models.ForeignKey(
        'diets.TipoComida',
        on_delete=models.PROTECT,
        related_name='sustituciones_cliente',
        verbose_name="Momento del día"
    )
    receta_original = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.PROTECT,
        related_name='sustituciones_cliente_original',
        verbose_name="Receta original"
    )
    receta_sustituta = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.PROTECT,
        related_name='sustituciones_cliente_sustituta',
        verbose_name="Receta sustituta"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Sustitución por cliente (fecha)"
        verbose_name_plural = "Sustituciones por cliente"
        unique_together = ['fecha', 'contrato', 'tipo_comida', 'receta_original']
        ordering = ['fecha', 'contrato', 'tipo_comida']

    def __str__(self):
        return f"{self.fecha} - {self.contrato.cliente.nombre}: {self.tipo_comida.nombre} → {self.receta_sustituta.nombre}"


class PlanificacionDieta(models.Model):
    """Modelo para gestionar la planificación de dietas por fecha"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('completada', 'Completada'),
    ]

    fecha = models.DateField(verbose_name="Fecha")
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='planificaciones',
        verbose_name="Contrato"
    )
    dieta = models.ForeignKey(
        'diets.Dieta',
        on_delete=models.PROTECT,
        related_name='planificaciones',
        verbose_name="Dieta"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")
    recetas_alternativas = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Recetas alternativas sugeridas",
        help_text="Lista de IDs de recetas alternativas sugeridas por el sistema"
    )

    class Meta:
        verbose_name = "Planificación de Dieta"
        verbose_name_plural = "Planificaciones de Dietas"
        unique_together = ['fecha', 'contrato']
        ordering = ['fecha', 'contrato']

    def __str__(self):
        return f"{self.fecha} - {self.contrato.cliente.nombre} - {self.dieta.nombre}"

    def clean(self):
        """Validación personalizada"""
        # Verificar que el contrato esté activo
        if not self.contrato.esta_activo():
            raise ValidationError("El contrato debe estar activo para planificar dietas.")

        # Verificar que la fecha esté dentro del rango del contrato
        if self.fecha < self.contrato.fecha_inicio:
            raise ValidationError("La fecha no puede ser anterior a la fecha de inicio del contrato.")
        
        if self.contrato.fecha_fin and self.fecha > self.contrato.fecha_fin:
            raise ValidationError("La fecha no puede ser posterior a la fecha de fin del contrato.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PlanificacionRecetaSustituta(models.Model):
    """
    Sustitución individualizada de una receta en una planificación: para un cliente/fecha,
    en un momento del día, se usa receta_sustituta en lugar de receta_original (por
    ingredientes que no le gustan al cliente u otra razón).
    """
    planificacion = models.ForeignKey(
        PlanificacionDieta,
        on_delete=models.CASCADE,
        related_name='sustituciones',
        verbose_name="Planificación"
    )
    tipo_comida = models.ForeignKey(
        'diets.TipoComida',
        on_delete=models.PROTECT,
        related_name='sustituciones_planificacion',
        verbose_name="Momento / Tipo de comida"
    )
    receta_original = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.PROTECT,
        related_name='sustituciones_como_original',
        verbose_name="Receta original"
    )
    receta_sustituta = models.ForeignKey(
        'recipes.Receta',
        on_delete=models.PROTECT,
        related_name='sustituciones_como_sustituta',
        verbose_name="Receta sustituta"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Sustitución de receta"
        verbose_name_plural = "Sustituciones de recetas"
        unique_together = ['planificacion', 'tipo_comida', 'receta_original']
        ordering = ['planificacion', 'tipo_comida']

    def __str__(self):
        return f"{self.planificacion} - {self.tipo_comida.nombre}: {self.receta_original.nombre} → {self.receta_sustituta.nombre}"
