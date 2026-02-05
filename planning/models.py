from django.db import models
from django.core.exceptions import ValidationError


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
