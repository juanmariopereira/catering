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
