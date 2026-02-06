from django.db import models
from django.core.validators import EmailValidator


class Cliente(models.Model):
    """Modelo para gestionar clientes del sistema de catering"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre completo")
    email = models.EmailField(validators=[EmailValidator()], verbose_name="Email")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    direccion = models.TextField(
        blank=True,
        default='',
        verbose_name="Dirección",
        help_text="Dirección literal del cliente"
    )
    link_maps = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        verbose_name="Enlace Google Maps",
        help_text="URL de Google Maps con la ubicación (opcional)"
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Latitud",
        help_text="Coordenada para mapas y optimización de rutas (Google Maps)"
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Longitud",
        help_text="Coordenada para mapas y optimización de rutas (Google Maps)"
    )
    titular = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependientes',
        verbose_name="Cliente titular",
        help_text="Si este cliente es dependiente de otro (ej. familiar), indique el cliente titular para cobranzas."
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def tiene_contratos_vigentes(self):
        """
        True si el cliente tiene al menos un contrato no cancelado (activo, pausado o vencido).
        Usado para mostrar estado "Sin Contrato" cuando no tiene contratos vigentes.
        """
        from contracts.models import Contrato, q_filtro_estado
        q = q_filtro_estado('activo') | q_filtro_estado('pausado') | q_filtro_estado('vencido')
        return self.contratos.filter(q).exists()


class IngredienteNoGustado(models.Model):
    """Relación entre Cliente e Ingrediente para ingredientes que no le gustan al cliente"""
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='ingredientes_no_gustados',
        verbose_name="Cliente"
    )
    ingrediente = models.ForeignKey(
        'recipes.Ingrediente',
        on_delete=models.CASCADE,
        related_name='clientes_que_no_gustan',
        verbose_name="Ingrediente"
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de agregado")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Actualizado")
    motivo = models.TextField(blank=True, null=True, verbose_name="Motivo", help_text="Razón por la que no le gusta este ingrediente")

    class Meta:
        verbose_name = "Ingrediente No Gustado"
        verbose_name_plural = "Ingredientes No Gustados"
        unique_together = ['cliente', 'ingrediente']
        ordering = ['cliente', 'ingrediente']

    def __str__(self):
        return f"{self.cliente.nombre} - {self.ingrediente.nombre}"
