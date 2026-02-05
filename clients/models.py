from django.db import models
from django.core.validators import EmailValidator


class Cliente(models.Model):
    """Modelo para gestionar clientes del sistema de catering"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre completo")
    email = models.EmailField(validators=[EmailValidator()], verbose_name="Email")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    direcciones = models.JSONField(
        default=list,
        verbose_name="Direcciones",
        help_text="Lista de direcciones del cliente en formato JSON"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


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
    motivo = models.TextField(blank=True, null=True, verbose_name="Motivo", help_text="Razón por la que no le gusta este ingrediente")

    class Meta:
        verbose_name = "Ingrediente No Gustado"
        verbose_name_plural = "Ingredientes No Gustados"
        unique_together = ['cliente', 'ingrediente']
        ordering = ['cliente', 'ingrediente']

    def __str__(self):
        return f"{self.cliente.nombre} - {self.ingrediente.nombre}"
