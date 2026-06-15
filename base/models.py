"""
Modelos base del proyecto.
"""
from django.conf import settings
from django.db import models


class AIRequestLog(models.Model):
    """
    Registro de solicitudes a la API de IA para seguimiento de uso y costes.
    Incluye métricas de tokens (esfuerzo computacional de la IA).
    """
    ACCION_CHOICES = [
        ('estimar_nutricion_ingrediente', 'Estimar nutrición ingrediente'),
        ('estimar_nutricion_receta', 'Estimar nutrición receta'),
        ('sugerir_descripcion_receta', 'Sugerir descripción receta'),
        ('sugerir_ingredientes_receta', 'Sugerir ingredientes receta'),
        ('sugerir_dieta', 'Sugerir dieta personalizada'),
        ('sugerir_menu', 'Sugerir menú'),
        ('importar_receta', 'Importar receta desde texto'),
        ('generar_mensaje_cliente', 'Generar mensaje personalizado cliente'),
    ]

    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    accion = models.CharField(max_length=50, choices=ACCION_CHOICES, db_index=True)
    modelo = models.CharField(max_length=64, default='gpt-4o-mini')

    # Métricas de esfuerzo (tokens)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    exito = models.BooleanField(default=True)
    mensaje_error = models.TextField(blank=True)

    # Referencia opcional al objeto relacionado
    objeto_tipo = models.CharField(max_length=32, blank=True)  # 'receta', 'ingrediente', 'plan'
    objeto_id = models.PositiveIntegerField(null=True, blank=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_request_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Log de solicitud IA'
        verbose_name_plural = 'Logs de solicitudes IA'

    def __str__(self):
        return f"{self.accion} ({self.total_tokens} tokens) - {self.fecha_hora}"


class ExternalApiRequestLog(models.Model):
    """
    Registro de solicitudes a APIs externas (Google Maps, etc.) para auditoría,
    uso y depuración. Guarda parámetros de request (sin clave API en claro),
    estado de respuesta y resumen del cuerpo.
    """
    API_CHOICES = [
        ('google_directions', 'Google Directions API'),
        ('google_geocoding', 'Google Geocoding API'),
        ('google_places', 'Google Places API'),
    ]

    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    api = models.CharField(max_length=32, choices=API_CHOICES, db_index=True)
    endpoint = models.CharField(max_length=512, blank=True, help_text='URL base del endpoint (sin query)')

    # Request: sin incluir API key en texto plano
    request_params = models.JSONField(default=dict, blank=True, help_text='Parámetros enviados (key enmascarada)')
    request_extra = models.TextField(blank=True, help_text='Otros datos del request (ej. waypoints count)')

    # Response
    response_status = models.CharField(max_length=64, blank=True, db_index=True)
    response_body = models.JSONField(default=dict, blank=True, help_text='Resumen o fragmento de la respuesta')
    exito = models.BooleanField(default=False)
    mensaje_error = models.TextField(blank=True)

    duracion_ms = models.PositiveIntegerField(null=True, blank=True)
    objeto_tipo = models.CharField(max_length=32, blank=True, db_index=True)
    objeto_id = models.PositiveIntegerField(null=True, blank=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_api_request_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Log de solicitud API externa'
        verbose_name_plural = 'Logs de solicitudes API externas'

    def __str__(self):
        return f"{self.api} {self.response_status} - {self.fecha_hora}"


class Feriado(models.Model):
    """
    Feriado (día festivo): no hay entregas y no cuenta como día de entrega
    en pausas de contrato, planificación, etc.
    """
    fecha = models.DateField(unique=True, verbose_name="Fecha", db_index=True)
    nombre = models.CharField(max_length=255, verbose_name="Nombre")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['fecha']
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"

    def __str__(self):
        return f"{self.nombre} ({self.fecha})"


def es_feriado(fecha):
    """Indica si la fecha dada es un feriado."""
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    return Feriado.objects.filter(fecha=fecha).exists()


def get_feriado(fecha):
    """Devuelve el Feriado para la fecha, o None si no es feriado."""
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    return Feriado.objects.filter(fecha=fecha).first()


def feriados_en_rango(fecha_inicio, fecha_fin):
    """Devuelve un set de fechas (date) que son feriados entre fecha_inicio y fecha_fin (inclusive)."""
    if hasattr(fecha_inicio, 'date'):
        fecha_inicio = fecha_inicio.date()
    if hasattr(fecha_fin, 'date'):
        fecha_fin = fecha_fin.date()
    return set(
        Feriado.objects.filter(
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        ).values_list('fecha', flat=True)
    )


class ParametroSistema(models.Model):
    """
    Parámetros básicos del sistema (clave/valor). Permite configurar opciones
    sin cambiar código (ej. textos, límites, flags).
    """
    clave = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Clave",
        help_text="Identificador único del parámetro (ej. nombre_empresa, dias_aviso_vencimiento)",
    )
    valor = models.TextField(
        blank=True,
        default="",
        verbose_name="Valor",
        help_text="Valor del parámetro (texto o número)",
    )
    descripcion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Descripción",
        help_text="Descripción opcional para saber para qué sirve",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ["clave"]
        verbose_name = "Parámetro del sistema"
        verbose_name_plural = "Parámetros del sistema"

    def __str__(self):
        return f"{self.clave} = {self.valor[:50]}{'…' if len(self.valor or '') > 50 else ''}"


class UserActionLog(models.Model):
    """
    Historial de acciones de usuarios en la aplicación (crear, editar, eliminar).
    Permite auditoría y consulta de quién hizo qué y qué cambios se realizaron.
    """
    ACCION_CHOICES = [
        ('crear', 'Crear'),
        ('editar', 'Editar'),
        ('eliminar', 'Eliminar'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_action_logs',
        verbose_name='Usuario',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha y hora')
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES, db_index=True, verbose_name='Acción')
    modelo = models.CharField(max_length=64, db_index=True, verbose_name='Tipo de registro')
    objeto_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID del objeto')
    objeto_repr = models.CharField(max_length=255, blank=True, verbose_name='Descripción del objeto')
    descripcion = models.TextField(blank=True, verbose_name='Descripción adicional')
    # Cambios en ediciones: lista de {"campo": str, "valor_anterior": str, "valor_nuevo": str}
    cambios = models.JSONField(default=list, blank=True, verbose_name='Cambios realizados')

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Registro de acción de usuario'
        verbose_name_plural = 'Historial de acciones de usuarios'

    def __str__(self):
        user = self.usuario.get_username() if self.usuario else '—'
        return f"{user} | {self.get_accion_display()} | {self.modelo} | {self.fecha_hora}"


class ProveedorIA(models.Model):
    """
    Proveedor de IA (OpenAI, Anthropic, Gemini, Grok). Guarda la clave API y si
    está habilitado. OpenAI, Gemini y Grok se consumen vía el SDK de OpenAI
    (endpoint compatible); Anthropic vía su propio SDK.
    """
    CODIGO_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google Gemini'),
        ('grok', 'xAI Grok'),
    ]

    codigo = models.CharField(
        max_length=20,
        unique=True,
        choices=CODIGO_CHOICES,
        verbose_name='Proveedor',
        help_text='Proveedor de IA. Determina el SDK y el endpoint usados.',
    )
    nombre = models.CharField(max_length=100, blank=True, verbose_name='Nombre visible')
    api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Clave API',
        help_text='Clave de API del proveedor. Si está vacía, el proveedor no se puede usar.',
    )
    activo = models.BooleanField(
        default=False,
        verbose_name='Habilitado',
        help_text='Si está deshabilitado, ninguno de sus modelos se podrá usar.',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Proveedor de IA'
        verbose_name_plural = 'Proveedores de IA'

    def __str__(self):
        return self.nombre or self.get_codigo_display()

    @property
    def disponible(self):
        return self.activo and bool((self.api_key or '').strip())


class ModeloIA(models.Model):
    """
    Modelo concreto de un proveedor (ej. gpt-4o-mini, claude-opus-4-8,
    gemini-2.0-flash, grok-2-latest), con sus límites de uso editables.
    Un límite en 0 significa "sin límite".
    """
    proveedor = models.ForeignKey(
        ProveedorIA,
        on_delete=models.CASCADE,
        related_name='modelos',
        verbose_name='Proveedor',
    )
    modelo_id = models.CharField(
        max_length=100,
        verbose_name='ID del modelo',
        help_text='Identificador exacto del modelo en el proveedor (ej. gpt-4o-mini, claude-opus-4-8).',
    )
    nombre = models.CharField(max_length=120, blank=True, verbose_name='Nombre visible')
    activo = models.BooleanField(default=True, verbose_name='Habilitado')

    # Límites de uso (0 = sin límite). Valores por defecto editables.
    tokens_por_minuto = models.PositiveIntegerField(default=100000, verbose_name='Tokens por minuto')
    tokens_por_dia = models.PositiveIntegerField(default=2000000, verbose_name='Tokens por día')
    requests_por_minuto = models.PositiveIntegerField(default=60, verbose_name='Solicitudes por minuto')
    requests_por_dia = models.PositiveIntegerField(default=5000, verbose_name='Solicitudes por día')

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['proveedor__codigo', 'modelo_id']
        verbose_name = 'Modelo de IA'
        verbose_name_plural = 'Modelos de IA'
        constraints = [
            models.UniqueConstraint(fields=['proveedor', 'modelo_id'], name='uniq_proveedor_modelo'),
        ]

    def __str__(self):
        return self.nombre or f"{self.proveedor.get_codigo_display()} · {self.modelo_id}"

    @property
    def disponible(self):
        return self.activo and self.proveedor.disponible

    def _limites_en_defecto_generico(self):
        from base.ai_catalog import DEFAULTS_GENERICOS
        return all(
            getattr(self, k) == DEFAULTS_GENERICOS[k]
            for k in ('tokens_por_minuto', 'tokens_por_dia', 'requests_por_minuto', 'requests_por_dia')
        )

    def save(self, *args, **kwargs):
        # Defaults dinámicos: al crear un modelo cuyos límites siguen en el valor
        # genérico, se rellenan con los recomendados para ese modelo_id (catálogo).
        if self._state.adding and self.proveedor_id and self._limites_en_defecto_generico():
            from base.ai_catalog import defaults_para
            for k, v in defaults_para(self.modelo_id, self.proveedor.codigo).items():
                setattr(self, k, v)
        super().save(*args, **kwargs)


class AsignacionUsoIA(models.Model):
    """
    Asigna modelos de IA a cada tipo de uso del sistema (acción de
    AIRequestLog.ACCION_CHOICES) formando una cadena de fallback ordenada por
    prioridad: para un mismo uso puede haber varias filas con distinto ``orden``.

    El sistema usa el modelo de menor ``orden`` disponible; si falla, no está
    disponible o supera su límite, pasa al siguiente en la jerarquía.
    """
    accion = models.CharField(
        max_length=50,
        db_index=True,
        choices=AIRequestLog.ACCION_CHOICES,
        verbose_name='Uso de IA',
    )
    modelo = models.ForeignKey(
        ModeloIA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones',
        verbose_name='Modelo asignado',
    )
    orden = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Orden (prioridad)',
        help_text='Menor = mayor prioridad. Si este modelo falla o no está disponible, '
                  'se intenta el siguiente del mismo uso.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Habilitado',
        help_text='Si está deshabilitado, este nivel se omite de la cadena de fallback.',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        ordering = ['accion', 'orden']
        verbose_name = 'Asignación de uso de IA'
        verbose_name_plural = 'Asignaciones de uso de IA'
        constraints = [
            models.UniqueConstraint(fields=['accion', 'modelo'], name='uniq_accion_modelo'),
        ]

    def __str__(self):
        return f"{self.get_accion_display()} #{self.orden} → {self.modelo or '—'}"
