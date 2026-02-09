from django.db import models
from django.conf import settings


class Reclamo(models.Model):
    """
    Reclamo o consulta recibida por WhatsApp.
    Se vincula al cliente si el teléfono coincide con un Cliente.telefono.
    """
    TIPO_CHOICES = [
        ('reclamo', 'Reclamo'),
        ('consulta', 'Consulta'),
        ('otro', 'Otro'),
    ]

    cliente = models.ForeignKey(
        'clients.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reclamos_whatsapp',
        verbose_name='Cliente',
    )
    telefono_whatsapp = models.CharField(
        max_length=30,
        verbose_name='Teléfono WhatsApp',
        help_text='Número desde el que se envió el mensaje (con código de país si aplica).',
    )
    mensaje = models.TextField(verbose_name='Mensaje')
    mensaje_id_whatsapp = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID mensaje WhatsApp',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='reclamo',
        verbose_name='Tipo',
    )
    leido = models.BooleanField(default=False, verbose_name='Leído')
    respondido = models.BooleanField(default=False, verbose_name='Respondido')
    notas_internas = models.TextField(blank=True, null=True, verbose_name='Notas internas')
    fecha_recibido = models.DateTimeField(auto_now_add=True, verbose_name='Fecha recibido')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = 'Reclamo / consulta WhatsApp'
        verbose_name_plural = 'Reclamos / consultas WhatsApp'
        ordering = ['-fecha_recibido']

    def __str__(self):
        nombre = self.cliente.nombre if self.cliente else self.telefono_whatsapp
        return f"{nombre} — {self.get_tipo_display()} ({self.fecha_recibido.date()})"
