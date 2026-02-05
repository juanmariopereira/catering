from django.db import models
from django.core.validators import MinValueValidator


class DetalleCocina(models.Model):
    """
    Modelo para gestionar detalles de platos a elaborar por fecha.
    Este modelo agrupa las planificaciones por fecha mostrando recetas a preparar.
    """
    fecha = models.DateField(verbose_name="Fecha", unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas para el cocinero")

    class Meta:
        verbose_name = "Detalle de Cocina"
        verbose_name_plural = "Detalles de Cocina"
        ordering = ['-fecha']

    def __str__(self):
        return f"Detalle Cocina - {self.fecha}"

    @classmethod
    def obtener_recetas_por_fecha(cls, fecha):
        """
        Obtiene todas las recetas a preparar para una fecha específica,
        agrupadas por receta con la cantidad total
        """
        from planning.models import PlanificacionDieta
        from diets.models import DietaReceta
        from collections import defaultdict

        # Obtener todas las planificaciones para esta fecha
        planificaciones = PlanificacionDieta.objects.filter(
            fecha=fecha,
            estado__in=['pendiente', 'en_preparacion']
        )

        # Agrupar recetas y contar cantidad
        recetas_dict = defaultdict(int)
        recetas_info = {}

        for planificacion in planificaciones:
            # Obtener recetas de la dieta
            dieta_recetas = DietaReceta.objects.filter(dieta=planificacion.dieta)
            
            for dieta_receta in dieta_recetas:
                receta = dieta_receta.receta
                recetas_dict[receta.id] += 1
                
                if receta.id not in recetas_info:
                    recetas_info[receta.id] = {
                        'receta': receta,
                        'cantidad': 0,
                        'planificaciones': []
                    }
                
                recetas_info[receta.id]['cantidad'] = recetas_dict[receta.id]
                recetas_info[receta.id]['planificaciones'].append(planificacion)

        return list(recetas_info.values())
