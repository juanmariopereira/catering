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

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Log de solicitud IA'
        verbose_name_plural = 'Logs de solicitudes IA'

    def __str__(self):
        return f"{self.accion} ({self.total_tokens} tokens) - {self.fecha_hora}"
