from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta


def _dias_vencimiento_por_frecuencia(frecuencia_pago):
    """Días después de periodo_hasta para calcular fecha_vencimiento del cobro."""
    if frecuencia_pago == 'mensual':
        return 15
    return 7  # diario, semanal, quincenal


class Cobro(models.Model):
    """
    Cobro vinculado a un contrato vigente. Representa un cargo por un período
    de servicio (periodo_desde / periodo_hasta). La fecha de vencimiento se
    define automáticamente según el contrato si no se indica.
    """
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
    ]

    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.PROTECT,
        related_name='cobros',
        verbose_name="Contrato"
    )
    periodo_desde = models.DateField(verbose_name="Período desde")
    periodo_hasta = models.DateField(verbose_name="Período hasta")
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto"
    )
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de vencimiento",
        help_text="Se calcula automáticamente si se deja vacío (según período y frecuencia del contrato)."
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    numero_cobro = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Número de cobro"
    )
    fecha_generacion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de generación",
        help_text="Fecha en que se generó el cobro (opcional)."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Cobro"
        verbose_name_plural = "Cobros"
        ordering = ['-periodo_hasta', '-numero_cobro']

    def __str__(self):
        if self.numero_cobro:
            return f"Cobro {self.numero_cobro} - {self.contrato.cliente.nombre}"
        return f"Cobro {self.id} - {self.contrato.cliente.nombre}"

    def calcular_monto_pagado(self):
        """Calcula el monto total pagado de este cobro."""
        from django.db.models import Sum
        return self.pagos.aggregate(total=Sum('monto'))['total'] or 0

    def monto_pendiente(self):
        """Calcula el monto pendiente de pago."""
        return self.monto - self.calcular_monto_pagado()

    def actualizar_estado(self):
        """Actualiza el estado del cobro según pagos y fecha de vencimiento."""
        monto_pagado = self.calcular_monto_pagado()
        if monto_pagado >= self.monto:
            nuevo_estado = 'pagada'
        elif timezone.now().date() > self.fecha_vencimiento:
            nuevo_estado = 'vencida'
        else:
            nuevo_estado = 'pendiente'
        self.estado = nuevo_estado
        Cobro.objects.filter(pk=self.pk).update(estado=nuevo_estado)

    def _calcular_fecha_vencimiento_auto(self):
        """Calcula fecha de vencimiento según periodo_hasta y frecuencia del contrato."""
        dias = _dias_vencimiento_por_frecuencia(self.contrato.frecuencia_pago)
        return self.periodo_hasta + timedelta(days=dias)

    def save(self, *args, **kwargs):
        if not self.fecha_vencimiento and self.periodo_hasta and self.contrato_id:
            contrato = self.contrato if hasattr(self, 'contrato') else None
            if contrato is None:
                from contracts.models import Contrato
                contrato = Contrato.objects.filter(pk=self.contrato_id).first()
            if contrato:
                self.fecha_vencimiento = self.periodo_hasta + timedelta(
                    days=_dias_vencimiento_por_frecuencia(contrato.frecuencia_pago)
                )
        if not self.fecha_generacion:
            self.fecha_generacion = timezone.now().date()
        if not self.numero_cobro:
            fecha_str = (self.fecha_generacion or timezone.now().date()).strftime('%Y%m%d')
            ultimo = Cobro.objects.filter(
                numero_cobro__startswith=f'COB-{fecha_str}'
            ).order_by('-numero_cobro').first()
            if ultimo and ultimo.numero_cobro:
                try:
                    n = int(ultimo.numero_cobro.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    n = 1
            else:
                n = 1
            self.numero_cobro = f'COB-{fecha_str}-{n:04d}'
        super().save(*args, **kwargs)
        self.actualizar_estado()
        _extender_contrato_si_cobro_posterior(self)


def _extender_contrato_si_cobro_posterior(cobro):
    """
    Si el cobro tiene periodo_hasta posterior a la fecha_fin del contrato,
    actualiza la fecha_fin del contrato (reactiva/extiende el contrato).
    Se llama al guardar un Cobro o un Pago.
    """
    if not cobro.periodo_hasta or not getattr(cobro, 'contrato_id', None):
        return
    from contracts.models import Contrato
    contrato = getattr(cobro, 'contrato', None) or Contrato.objects.filter(pk=cobro.contrato_id).first()
    if contrato and (contrato.fecha_fin is None or cobro.periodo_hasta > contrato.fecha_fin):
        Contrato.objects.filter(pk=contrato.pk).update(fecha_fin=cobro.periodo_hasta)


class Pago(models.Model):
    """Modelo para gestionar pagos de cobros."""
    METODO_PAGO_CHOICES = [
        ('qr', 'QR'),
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ]

    cobro = models.ForeignKey(
        Cobro,
        on_delete=models.CASCADE,
        related_name='pagos',
        verbose_name="Cobro"
    )
    fecha_pago = models.DateField(verbose_name="Fecha de pago")
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto"
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        default='qr',
        verbose_name="Método de pago"
    )
    referencia = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Referencia",
        help_text="Número de referencia, comprobante, etc."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ['-fecha_pago', '-fecha_creacion']

    def __str__(self):
        return f"Pago {self.monto} - {self.cobro} ({self.get_metodo_pago_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cobro.actualizar_estado()
        _extender_contrato_si_cobro_posterior(self.cobro)

    def delete(self, *args, **kwargs):
        cobro = self.cobro
        super().delete(*args, **kwargs)
        cobro.actualizar_estado()
