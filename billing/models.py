from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta


class Factura(models.Model):
    """Modelo para gestionar facturas"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
    ]

    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.PROTECT,
        related_name='facturas',
        verbose_name="Contrato"
    )
    fecha_emision = models.DateField(verbose_name="Fecha de emisión")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de vencimiento")
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    periodo_desde = models.DateField(verbose_name="Período desde")
    periodo_hasta = models.DateField(verbose_name="Período hasta")
    numero_factura = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Número de factura"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision', '-numero_factura']

    def __str__(self):
        if self.numero_factura:
            return f"Factura {self.numero_factura} - {self.contrato.cliente.nombre}"
        return f"Factura {self.id} - {self.contrato.cliente.nombre}"

    def calcular_monto_pagado(self):
        """Calcula el monto total pagado de esta factura"""
        from django.db.models import Sum
        return self.pagos.aggregate(total=Sum('monto'))['total'] or 0

    def monto_pendiente(self):
        """Calcula el monto pendiente de pago"""
        return self.monto - self.calcular_monto_pagado()

    def actualizar_estado(self):
        """Actualiza el estado de la factura según pagos y fecha de vencimiento"""
        monto_pagado = self.calcular_monto_pagado()
        if monto_pagado >= self.monto:
            nuevo_estado = 'pagada'
        elif timezone.now().date() > self.fecha_vencimiento:
            nuevo_estado = 'vencida'
        else:
            nuevo_estado = 'pendiente'
        self.estado = nuevo_estado
        Factura.objects.filter(pk=self.pk).update(estado=nuevo_estado)

    def save(self, *args, **kwargs):
        # Generar número de factura si no existe
        if not self.numero_factura:
            # Formato: FACT-YYYYMMDD-XXXX
            fecha_str = self.fecha_emision.strftime('%Y%m%d')
            ultima_factura = Factura.objects.filter(
                numero_factura__startswith=f'FACT-{fecha_str}'
            ).order_by('-numero_factura').first()
            
            if ultima_factura and ultima_factura.numero_factura:
                try:
                    ultimo_numero = int(ultima_factura.numero_factura.split('-')[-1])
                    nuevo_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    nuevo_numero = 1
            else:
                nuevo_numero = 1
            
            self.numero_factura = f'FACT-{fecha_str}-{nuevo_numero:04d}'
        
        super().save(*args, **kwargs)
        
        # Actualizar estado después de guardar
        self.actualizar_estado()


class Pago(models.Model):
    """Modelo para gestionar pagos de facturas"""
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ]

    factura = models.ForeignKey(
        Factura,
        on_delete=models.CASCADE,
        related_name='pagos',
        verbose_name="Factura"
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
        return f"Pago {self.monto} - {self.factura} ({self.get_metodo_pago_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar estado de la factura después de guardar el pago
        self.factura.actualizar_estado()

    def delete(self, *args, **kwargs):
        factura = self.factura
        super().delete(*args, **kwargs)
        # Actualizar estado de la factura después de eliminar el pago
        factura.actualizar_estado()
