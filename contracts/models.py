from datetime import timedelta

from django.db import models
from django.db.models import Q, Count
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
        default='mensual',
        verbose_name="Frecuencia de pago"
    )
    direccion_entrega = models.TextField(
        blank=True,
        default='',
        verbose_name="Dirección de entrega",
        help_text="Dirección completa donde se entrega el servicio"
    )
    link_maps = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        verbose_name="Enlace Google Maps",
        help_text="URL de Google Maps con la ubicación (opcional)"
    )
    horario_entrega = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Horario de entrega",
        help_text="Hora de entrega (ej. 08:30)"
    )
    dias_entrega = models.JSONField(
        default=list,
        verbose_name="Días de entrega",
        help_text="Días de la semana en que se entrega el servicio (lunes, martes, …)"
    )
    notas_entregador = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas para el entregador",
        help_text="Indicaciones opcionales para quien realiza la entrega (ej. timbre, dejar en conserjería)"
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
        """Método para pausar el contrato (estado global)"""
        if self.estado == 'activo':
            self.estado = 'pausado'
            self.fecha_pausa = timezone.now()
            self.save()

    def reanudar(self):
        """Método para reanudar el contrato (estado global)"""
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
        """Verifica si el contrato está activo (hoy)"""
        return self.activo_en_fecha(timezone.now().date())

    def activo_en_fecha(self, fecha):
        """
        Verifica si el contrato estaba activo en una fecha dada (para planificación).
        Devuelve False si el contrato está cancelado, pausado globalmente,
        fuera de rango, o dentro de alguna pausa por fechas (PausaContrato).
        """
        if self.estado == 'cancelado':
            return False
        if self.estado == 'pausado':
            return False
        if fecha < self.fecha_inicio:
            return False
        if self.fecha_fin is not None and fecha > self.fecha_fin:
            return False
        if self.pausas.filter(fecha_inicio__lte=fecha, fecha_fin__gte=fecha).exists():
            return False
        return True


def contratos_activos_en_fecha(fecha):
    """
    Contratos que están activos en la fecha dada (estado activo, en rango, y no en pausa).
    Uso: planning, entregas, cocina, etc.
    """
    return Contrato.objects.filter(
        estado='activo',
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).exclude(
        pausas__fecha_inicio__lte=fecha,
        pausas__fecha_fin__gte=fecha,
    ).distinct()


class PausaContrato(models.Model):
    """
    Pausa por fechas: el cliente no recibe servicio entre fecha_inicio y fecha_fin.
    Un contrato puede tener varias pausas (por ejemplo varias semanas en el mes).
    """
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='pausas',
        verbose_name="Contrato"
    )
    fecha_inicio = models.DateField(verbose_name="Fecha inicio pausa")
    fecha_fin = models.DateField(verbose_name="Fecha fin pausa")
    motivo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Motivo",
        help_text="Ej: vacaciones, viaje, etc."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Pausa de contrato"
        verbose_name_plural = "Pausas de contrato"
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"{self.contrato} — pausa {self.fecha_inicio} a {self.fecha_fin}"

    # Mapeo: Python date.weekday() 0=lunes, 6=domingo -> valor en dias_entrega del contrato
    _WEEKDAY_NOMBRE = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

    def _dias_pausa(self, fecha_inicio, fecha_fin):
        """
        Número de días de entrega (según dias_entrega del contrato) entre
        fecha_inicio y fecha_fin (inclusive). No se cuentan los feriados.
        Si el contrato no tiene días configurados, se usan días calendario.
        """
        from base.models import feriados_en_rango
        contrato = getattr(self, 'contrato', None)
        if contrato is None and self.contrato_id:
            contrato = Contrato.objects.filter(pk=self.contrato_id).first()
        dias_entrega = list(contrato.dias_entrega) if contrato and contrato.dias_entrega else []
        feriados = feriados_en_rango(fecha_inicio, fecha_fin)
        if not dias_entrega:
            return (fecha_fin - fecha_inicio).days + 1 - len(feriados)
        count = 0
        d = fecha_inicio
        while d <= fecha_fin:
            if d not in feriados and self._WEEKDAY_NOMBRE[d.weekday()] in dias_entrega:
                count += 1
            d += timedelta(days=1)
        return count

    def save(self, *args, **kwargs):
        """Al crear o modificar una pausa, se extiende fecha_fin del contrato por los días de pausa."""
        delta_days = 0
        if self.pk:
            try:
                old = PausaContrato.objects.get(pk=self.pk)
                old_days = self._dias_pausa(old.fecha_inicio, old.fecha_fin)
                new_days = self._dias_pausa(self.fecha_inicio, self.fecha_fin)
                delta_days = new_days - old_days
            except PausaContrato.DoesNotExist:
                new_days = self._dias_pausa(self.fecha_inicio, self.fecha_fin)
                delta_days = new_days
        else:
            delta_days = self._dias_pausa(self.fecha_inicio, self.fecha_fin)
        super().save(*args, **kwargs)
        if delta_days != 0 and self.contrato_id:
            contrato = Contrato.objects.get(pk=self.contrato_id)
            if contrato.fecha_fin:
                nueva_fin = contrato.fecha_fin + timedelta(days=delta_days)
                Contrato.objects.filter(pk=self.contrato_id).update(fecha_fin=nueva_fin)

    def delete(self, *args, **kwargs):
        """Al eliminar una pausa, se reduce fecha_fin del contrato por los días que tenía la pausa."""
        contrato_id = self.contrato_id
        dias = self._dias_pausa(self.fecha_inicio, self.fecha_fin)
        super().delete(*args, **kwargs)
        if contrato_id and dias:
            contrato = Contrato.objects.filter(pk=contrato_id).first()
            if contrato and contrato.fecha_fin:
                nueva_fin = contrato.fecha_fin - timedelta(days=dias)
                Contrato.objects.filter(pk=contrato_id).update(fecha_fin=nueva_fin)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha fin no puede ser anterior a la fecha inicio.")
        if self.contrato_id and self.fecha_inicio and self.contrato.fecha_fin and self.fecha_inicio > self.contrato.fecha_fin:
            raise ValidationError("La pausa no puede empezar después de la fecha fin del contrato.")
        if self.contrato_id and self.fecha_inicio and self.fecha_inicio < self.contrato.fecha_inicio:
            raise ValidationError("La pausa no puede empezar antes de la fecha inicio del contrato.")


def recalcular_fecha_fin_por_feriado(fecha, delta):
    """
    Ajusta fecha_fin de los contratos cuando cambia el calendario de feriados.
    - delta=+1: se agregó un feriado; cada pausa que contiene esa fecha pierde
      un día de entrega → se extiende fecha_fin en 1 día por cada tal pausa.
    - delta=-1: se quitó un feriado; cada pausa que contiene esa fecha gana
      un día de entrega → se acorta fecha_fin en 1 día por cada tal pausa.
    """
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    pausas_por_contrato = (
        PausaContrato.objects.filter(
            fecha_inicio__lte=fecha,
            fecha_fin__gte=fecha,
        )
        .values('contrato_id')
        .annotate(n=Count('id'))
    )
    for row in pausas_por_contrato:
        contrato_id = row['contrato_id']
        n = row['n']
        if n == 0:
            continue
        contrato = Contrato.objects.filter(pk=contrato_id).first()
        if contrato and contrato.fecha_fin is not None:
            days_delta = delta * n
            nueva_fin = contrato.fecha_fin + timedelta(days=days_delta)
            Contrato.objects.filter(pk=contrato_id).update(fecha_fin=nueva_fin)
