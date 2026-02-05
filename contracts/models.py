from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Contrato(models.Model):
    """Modelo para gestionar contratos de clientes"""
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('pausado', 'Pausado'),
        ('cancelado', 'Cancelado'),
    ]

    FRECUENCIA_PAGO_CHOICES = [
        ('diario', 'Diario'),
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ]

    DIA_SEMANA_CHOICES = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
        ('domingo', 'Domingo'),
    ]

    cliente = models.ForeignKey(
        'clients.Cliente',
        on_delete=models.CASCADE,
        related_name='contratos',
        verbose_name="Cliente"
    )
    plan = models.ForeignKey(
        'plans.Plan',
        on_delete=models.PROTECT,
        related_name='contratos',
        verbose_name="Plan"
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(blank=True, null=True, verbose_name="Fecha de fin")
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio"
    )
    frecuencia_pago = models.CharField(
        max_length=20,
        choices=FRECUENCIA_PAGO_CHOICES,
        verbose_name="Frecuencia de pago"
    )
    direccion_entrega = models.JSONField(
        default=dict,
        verbose_name="Dirección de entrega",
        help_text="Dirección de entrega en formato JSON"
    )
    horario_entrega = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Horario de entrega",
        help_text="Ej: 08:00 - 10:00"
    )
    dias_entrega = models.JSONField(
        default=list,
        verbose_name="Días de entrega",
        help_text="Lista de días de la semana en formato JSON"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='activo',
        verbose_name="Estado"
    )
    fecha_pausa = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de pausa"
    )
    fecha_reanudacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de reanudación"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.cliente.nombre} - {self.plan.nombre} ({self.get_estado_display()})"

    def pausar(self):
        """Método para pausar el contrato"""
        if self.estado == 'activo':
            self.estado = 'pausado'
            self.fecha_pausa = timezone.now()
            self.save()

    def reanudar(self):
        """Método para reanudar el contrato"""
        if self.estado == 'pausado':
            self.estado = 'activo'
            self.fecha_reanudacion = timezone.now()
            self.fecha_pausa = None
            self.save()

    def cancelar(self):
        """Método para cancelar el contrato"""
        self.estado = 'cancelado'
        self.save()

    def esta_activo(self):
        """Verifica si el contrato está activo"""
        return self.estado == 'activo' and (
            self.fecha_fin is None or self.fecha_fin >= timezone.now().date()
        )
