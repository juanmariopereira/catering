import uuid
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class PuntoEntrega(models.Model):
    """Ubicación física compartida por varios contratos (edificio, condominio, oficina)."""
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    latitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitud"
    )
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitud"
    )
    notas_acceso = models.TextField(
        blank=True,
        verbose_name="Notas de acceso",
        help_text="Portero, citófono, piso, código de acceso, etc.",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Punto de entrega"
        verbose_name_plural = "Puntos de entrega"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Entregador(models.Model):
    """Modelo para gestionar entregadores. Si user no es None, ese usuario tiene perfil Entregador y solo ve sus rutas."""
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
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregador_perfil',
        verbose_name="Usuario asociado",
        help_text="Usuario que inicia sesión como este entregador (solo ve sus rutas)."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    # Configuración de seguimiento GPS por entregador. Si es None, hereda el valor del
    # sistema (ParametroSistema). Permite afinar el comportamiento por repartidor.
    checkin_auto = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Check-in automático por GPS",
        help_text="Vacío = usar el valor del sistema. Marca la llegada automáticamente al entrar en el radio.",
    )
    checkin_radio_metros = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Radio de aproximación (m)",
        help_text="Vacío = usar el valor del sistema. Distancia para considerar que llegó a la parada.",
    )
    ping_intervalo_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Intervalo de envío GPS (s)",
        help_text="Vacío = usar el valor del sistema. Cada cuántos segundos la app envía su ubicación.",
    )

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


class PlantillaRuta(models.Model):
    """
    Plantilla de ruta por entregador: define qué contratos lleva cada entregador y en qué orden.
    La "ruta del día" se obtiene filtrando por activo_en_fecha(fecha) y dias_entrega.
    Una sola fila por entregador.
    """
    entregador = models.OneToOneField(
        Entregador,
        on_delete=models.CASCADE,
        related_name='plantilla_ruta',
        verbose_name="Entregador",
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas")
    duracion_legs_segundos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Duración por tramo (seg)",
        help_text="Lista de duraciones en segundos por tramo (desde API Directions).",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Plantilla de ruta"
        verbose_name_plural = "Plantillas de ruta"
        ordering = ['entregador__nombre']

    def __str__(self):
        return f"Plantilla - {self.entregador.nombre}"


class PlantillaRutaCliente(models.Model):
    """Asignación contrato → plantilla de entregador con orden de entrega."""
    codigo_entrega = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="Código de entrega",
        help_text="Identificador único corto para esta parada",
    )
    plantilla_ruta = models.ForeignKey(
        PlantillaRuta,
        on_delete=models.CASCADE,
        related_name='clientes',
        verbose_name="Plantilla",
    )
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='plantilla_rutas',
        verbose_name="Contrato",
    )
    orden_entrega = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Orden de entrega",
        help_text="Orden en que se realizará la entrega (mismo orden todos los días en que aplique)",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Cliente en plantilla"
        verbose_name_plural = "Clientes en plantilla"
        unique_together = ['plantilla_ruta', 'contrato']
        ordering = ['plantilla_ruta', 'orden_entrega']

    def save(self, *args, **kwargs):
        if not self.codigo_entrega:
            self.codigo_entrega = self._generar_codigo_unico()
        super().save(*args, **kwargs)

    def _generar_codigo_unico(self):
        for length in range(4, 13):
            for _ in range(100):
                codigo = uuid.uuid4().hex[:length].upper()
                if not PlantillaRutaCliente.objects.filter(codigo_entrega=codigo).exists():
                    return codigo
        return uuid.uuid4().hex[:12].upper()

    def __str__(self):
        return f"{self.plantilla_ruta} - {self.contrato.cliente.nombre} (#{self.orden_entrega})"


class EntregaDia(models.Model):
    """
    Estado de entrega de un contrato en una fecha para un entregador (entregada, no entregada, etc.).
    La lista de paradas del día se calcula desde PlantillaRutaCliente filtrada por fecha;
    este modelo solo guarda el estado del día.
    """
    entregador = models.ForeignKey(
        Entregador,
        on_delete=models.CASCADE,
        related_name='entregas_dia',
        verbose_name="Entregador",
    )
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='entregas_dia',
        verbose_name="Contrato",
    )
    fecha = models.DateField(verbose_name="Fecha")
    entregada = models.BooleanField(
        default=False,
        verbose_name="Entregada",
    )
    fecha_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha/hora entrega")
    marcadopor_entregada = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas_dia_marcadas',
        verbose_name="Marcado entregada por",
    )
    no_entregada = models.BooleanField(default=False, verbose_name="No entregada")
    motivo_no_entrega = models.TextField(blank=True, default='', verbose_name="Motivo no entrega")
    fecha_no_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha/hora reporte no entrega")
    marcadopor_no_entrega = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas_dia_no_entregada',
        verbose_name="Reportado no entrega por",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Entrega del día"
        verbose_name_plural = "Entregas del día"
        unique_together = ['entregador', 'contrato', 'fecha']
        ordering = ['fecha', 'entregador', 'contrato']

    def __str__(self):
        return f"{self.fecha} {self.entregador.nombre} - {self.contrato.cliente.nombre}"


class HistoricoAsignacionEntrega(models.Model):
    """
    Histórico de asignación: qué entregador tenía asignada la entrega de dieta
    a cada contrato en cada fecha. Se persiste con un comando (ej. crontab diario)
    a partir del estado de las plantillas y contratos con entrega ese día.
    Una fila por (fecha, contrato); planificacion_menu indica qué menú/dieta correspondía.
    """
    fecha = models.DateField(verbose_name="Fecha")
    contrato = models.ForeignKey(
        'contracts.Contrato',
        on_delete=models.CASCADE,
        related_name='historico_asignaciones_entrega',
        verbose_name="Contrato",
    )
    entregador = models.ForeignKey(
        Entregador,
        on_delete=models.PROTECT,
        related_name='historico_asignaciones_entrega',
        verbose_name="Entregador",
    )
    planificacion_menu = models.ForeignKey(
        'planning.PlanificacionMenu',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historico_asignaciones_entrega',
        verbose_name="Planificación menú (dieta del día)",
        help_text="Menú planificado para esa fecha y plan del contrato; null si no había menú.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")

    class Meta:
        verbose_name = "Histórico asignación entrega"
        verbose_name_plural = "Histórico asignaciones entrega"
        unique_together = [['fecha', 'contrato']]
        ordering = ['-fecha', 'entregador', 'contrato']

    def __str__(self):
        return f"{self.fecha} {self.entregador.nombre} → {self.contrato.cliente.nombre}"
