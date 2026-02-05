from django.db import models
from django.core.validators import MinValueValidator
from recipes.models import RecetaIngrediente, Ingrediente, UnidadMedida


class PrevisionCompra(models.Model):
    """Modelo para gestionar previsiones de compra de insumos"""
    fecha_generacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de generación")
    fecha_desde = models.DateField(verbose_name="Fecha desde")
    fecha_hasta = models.DateField(verbose_name="Fecha hasta")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Previsión de Compra"
        verbose_name_plural = "Previsiones de Compra"
        ordering = ['-fecha_generacion']

    def __str__(self):
        return f"Previsión {self.fecha_desde} - {self.fecha_hasta}"

    def calcular_items(self):
        """
        Calcula los items de la previsión basándose en los menús planificados
        (PlanificacionMenu) en el rango de fechas, aplicando sustituciones por cliente.
        """
        from planning.utils import ingredientes_por_rango_fechas
        ingredientes_totales = ingredientes_por_rango_fechas(
            self.fecha_desde,
            self.fecha_hasta,
        )
        PrevisionCompraItem.objects.filter(prevision=self).delete()
        for (ingrediente_id, unidad_id), cantidad_total in ingredientes_totales.items():
            PrevisionCompraItem.objects.create(
                prevision=self,
                ingrediente_id=ingrediente_id,
                cantidad_total=cantidad_total,
                unidad_medida_id=unidad_id
            )


class PrevisionCompraItem(models.Model):
    """Modelo para gestionar items de una previsión de compra"""
    prevision = models.ForeignKey(
        PrevisionCompra,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Previsión"
    )
    ingrediente = models.ForeignKey(
        'recipes.Ingrediente',
        on_delete=models.CASCADE,
        related_name='previsiones',
        verbose_name="Ingrediente"
    )
    cantidad_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Cantidad total"
    )
    unidad_medida = models.ForeignKey(
        'recipes.UnidadMedida',
        on_delete=models.PROTECT,
        related_name='prevision_items',
        verbose_name="Unidad de medida"
    )

    class Meta:
        verbose_name = "Item de Previsión de Compra"
        verbose_name_plural = "Items de Previsiones de Compra"
        unique_together = ['prevision', 'ingrediente', 'unidad_medida']
        ordering = ['prevision', 'ingrediente']

    def __str__(self):
        return f"{self.prevision} - {self.ingrediente.nombre}: {self.cantidad_total} {self.unidad_medida}"
