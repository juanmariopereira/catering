from django.contrib import admin
from .models import Dieta, DietaReceta


class DietaRecetaInline(admin.TabularInline):
    model = DietaReceta
    extra = 1
    ordering = ['orden']


@admin.register(Dieta)
class DietaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'plan', 'activa', 'fecha_creacion']
    list_filter = ['activa', 'plan', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    inlines = [DietaRecetaInline]
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'plan', 'activa')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion')
        }),
    )


@admin.register(DietaReceta)
class DietaRecetaAdmin(admin.ModelAdmin):
    list_display = ['dieta', 'receta', 'orden']
    list_filter = ['dieta', 'receta']
    search_fields = ['dieta__nombre', 'receta__nombre']
    ordering = ['dieta', 'orden']
