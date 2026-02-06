import uuid
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Entregador(models.Model):
    """Modelo para gestionar entregadores"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre completo")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    vehiculo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Vehículo",
        help_text="Tipo de vehículo utilizado para entregas"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Entregador"
        verbose_name_plural = "Entregadores"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Ruta(models.Model):
    """Modelo para gestionar rutas de entrega"""
    fecha = models.DateField(verbose_name="Fecha de la ruta")
    entregador = models.ForeignKey(
        Entregador,
        on_delete=models.PROTECT,
        related_name='rutas',
        verbose_name="Entregador"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")
    duracion_legs_segundos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Duración por tramo (seg)",
        help_text="Lista de duraciones en segundos por tramo (desde API Directions); se usa para tiempo estimado de llegada.",
    )

    clientes = models.ManyToManyField(
        'contracts.Contrato',
        through='RutaCliente',
        related_name='rutas',
        verbose_name="Clientes"
    )

    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        unique_together = ['fecha', 'entregador']
        ordering = ['-fecha', 'entregador']

    def __str__(self):
        return f"Ruta {self.fecha} - {self.entregador.nombre}"


class RutaCliente(models.Model):
    """Modelo intermedio para la relación many-to-many entre Ruta y Contrato con orden"""
    codigo_entrega = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="Código de entrega",
        help_text="Identificador único corto (4 caracteres por defecto; crece si hay colisión)"
    )
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.CASCADE,
        related_name='ruta_clientes',
        verbose_name="Ruta"
    )
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_rutas',
        verbose_name="Contrato"
    )
    orden_entrega = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Orden de entrega",
        help_text="Orden en que se realizará la entrega en esta ruta"
    )
    direccion_entrega = models.JSONField(
        default=dict,
        verbose_name="Dirección de entrega",
        help_text="Dirección específica para esta entrega en formato JSON"
    )
    entregada = models.BooleanField(
        default=False,
        verbose_name="Entregada",
        help_text="Marcado cuando se confirma la entrega en esta parada",
    )
    fecha_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha/hora entrega",
        help_text="Momento en que se marcó como entregada",
    )
    marcadopor_entregada = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas_marcadas_entregada',
        verbose_name="Marcado entregada por",
        help_text="Usuario que marcó esta parada como entregada",
    )
    no_entregada = models.BooleanField(
        default=False,
        verbose_name="No entregada",
        help_text="Marcado cuando se reporta que no se pudo realizar la entrega",
    )
    motivo_no_entrega = models.TextField(
        blank=True,
        default='',
        verbose_name="Motivo no entrega",
        help_text="Descripción obligatoria del motivo cuando no se pudo entregar",
    )
    fecha_no_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha/hora reporte no entrega",
        help_text="Momento en que se reportó que no se pudo entregar",
    )
    marcadopor_no_entrega = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas_marcadas_no_entregada',
        verbose_name="Reportado no entrega por",
        help_text="Usuario que reportó que no se pudo entregar",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Cliente de Ruta"
        verbose_name_plural = "Clientes de Rutas"
        unique_together = ['ruta', 'contrato']
        ordering = ['ruta', 'orden_entrega']

    def save(self, *args, **kwargs):
        if not self.codigo_entrega:
            self.codigo_entrega = self._generar_codigo_unico()
        super().save(*args, **kwargs)

    def _generar_codigo_unico(self):
        """Código corto: empieza en 4 caracteres y crece solo si hay colisión."""
        for length in range(4, 13):
            for _ in range(100):
                codigo = uuid.uuid4().hex[:length].upper()
                if not RutaCliente.objects.filter(codigo_entrega=codigo).exists():
                    return codigo
        return uuid.uuid4().hex[:12].upper()

    def __str__(self):
        return f"{self.ruta} - {self.contrato.cliente.nombre} (Orden: {self.orden_entrega})"
