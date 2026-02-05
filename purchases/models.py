from django.db import models
from django.core.validators import MinValueValidator
from planning.models import PlanificacionDieta
from recipes.models import RecetaIngrediente, Ingrediente


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
        Calcula automáticamente los items de la previsión basándose
        en las planificaciones de dietas en el rango de fechas
        """
        # Obtener todas las planificaciones en el rango de fechas
        planificaciones = PlanificacionDieta.objects.filter(
            fecha__gte=self.fecha_desde,
            fecha__lte=self.fecha_hasta,
            estado__in=['pendiente', 'en_preparacion']
        )

        # Agregar ingredientes de todas las recetas de las dietas planificadas
        ingredientes_totales = {}
        
        for planificacion in planificaciones:
            # Obtener todas las recetas de la dieta
            from diets.models import DietaReceta
            recetas_dieta = DietaReceta.objects.filter(dieta=planificacion.dieta)
            
            for dieta_receta in recetas_dieta:
                # Obtener ingredientes de la receta
                receta_ingredientes = RecetaIngrediente.objects.filter(
                    receta=dieta_receta.receta
                )
                
                for receta_ingrediente in receta_ingredientes:
                    ingrediente_id = receta_ingrediente.ingrediente_id
                    cantidad = receta_ingrediente.cantidad
                    unidad = receta_ingrediente.unidad_medida
                    
                    # Agregar a la suma total
                    key = (ingrediente_id, unidad)
                    if key not in ingredientes_totales:
                        ingredientes_totales[key] = 0
                    ingredientes_totales[key] += float(cantidad)
        
        # Crear o actualizar items de previsión
        PrevisionCompraItem.objects.filter(prevision=self).delete()
        
        for (ingrediente_id, unidad), cantidad_total in ingredientes_totales.items():
            PrevisionCompraItem.objects.create(
                prevision=self,
                ingrediente_id=ingrediente_id,
                cantidad_total=cantidad_total,
                unidad_medida=unidad
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
    unidad_medida = models.CharField(
        max_length=50,
        verbose_name="Unidad de medida"
    )

    class Meta:
        verbose_name = "Item de Previsión de Compra"
        verbose_name_plural = "Items de Previsiones de Compra"
        unique_together = ['prevision', 'ingrediente', 'unidad_medida']
        ordering = ['prevision', 'ingrediente']

    def __str__(self):
        return f"{self.prevision} - {self.ingrediente.nombre}: {self.cantidad_total} {self.unidad_medida}"
