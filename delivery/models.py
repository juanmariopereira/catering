from django.db import models


class PuntoPartidaEntrega(models.Model):
    """
    Configuración global del punto de partida para las rutas de entrega
    (ej. cocina, depósito). Solo se usa la primera fila; el algoritmo de
    optimización toma origen y destino desde aquí.
    """
    nombre = models.CharField(
        max_length=200,
        blank=True,
        default='Punto de partida',
        verbose_name="Nombre",
        help_text="Ej: Cocina central, Depósito"
    )
    direccion = models.TextField(
        blank=True,
        default='',
        verbose_name="Dirección",
        help_text="Dirección literal (opcional)"
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Latitud",
        help_text="Coordenada del punto de partida para optimizar rutas"
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Longitud",
        help_text="Coordenada del punto de partida para optimizar rutas"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está activo, el algoritmo usará este punto como origen y destino al reordenar entregas."
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Punto de partida (entregas)"
        verbose_name_plural = "Puntos de partida (entregas)"
        ordering = ['-fecha_actualizacion']

    def __str__(self):
        return self.nombre or f"Punto de partida ({self.latitud}, {self.longitud})"
