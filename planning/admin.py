from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PlanificacionMenu,
    PlanificacionMenuReceta,
    PlanificacionClienteSustituta,
    PlanificacionDieta,
)


class PlanificacionMenuRecetaInline(admin.TabularInline):
    model = PlanificacionMenuReceta
    extra = 2
    autocomplete_fields = ['receta']
    raw_id_fields = ['tipo_comida']


@admin.register(PlanificacionMenu)
class PlanificacionMenuAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'plan', 'fecha_creacion']
    list_filter = ['fecha', 'plan']
    date_hierarchy = 'fecha'
    inlines = [PlanificacionMenuRecetaInline]
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']


@admin.register(PlanificacionClienteSustituta)
class PlanificacionClienteSustitutaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'contrato', 'tipo_comida', 'receta_original', 'receta_sustituta']
    list_filter = ['fecha', 'tipo_comida']


@admin.register(PlanificacionDieta)
class PlanificacionDietaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'cliente', 'dieta', 'estado_badge', 'tiene_alternativas', 'fecha_creacion']
    list_filter = ['estado', 'fecha', 'dieta', 'fecha_creacion']
    search_fields = ['contrato__cliente__nombre', 'dieta__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'recetas_alternativas']
    date_hierarchy = 'fecha'
    fieldsets = (
        ('Información de Planificación', {
            'fields': ('fecha', 'contrato', 'dieta', 'estado')
        }),
        ('Sugerencias', {
            'fields': ('recetas_alternativas',),
            'description': 'Recetas alternativas sugeridas por el sistema'
        }),
        ('Información Adicional', {
            'fields': ('notas', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )

    def cliente(self, obj):
        return obj.contrato.cliente.nombre
    cliente.short_description = 'Cliente'

    def estado_badge(self, obj):
        colors = {
            'pendiente': 'orange',
            'en_preparacion': 'blue',
            'completada': 'green'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def tiene_alternativas(self, obj):
        if obj.recetas_alternativas:
            return format_html(
                '<span style="color: orange;">✓ {} sugerencias</span>',
                len(obj.recetas_alternativas)
            )
        return '-'
    tiene_alternativas.short_description = 'Alternativas'
