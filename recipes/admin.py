from django.contrib import admin
from .models import Ingrediente, Receta, RecetaIngrediente


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'unidad_medida', 'activo', 'fecha_creacion']
    list_filter = ['activo', 'unidad_medida', 'fecha_creacion']
    search_fields = ['nombre']
    readonly_fields = ['fecha_creacion']


class RecetaIngredienteInline(admin.TabularInline):
    model = RecetaIngrediente
    extra = 1


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'activa', 'fecha_creacion']
    list_filter = ['categoria', 'activa', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    inlines = [RecetaIngredienteInline]
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'categoria', 'activa')
        }),
        ('Información Nutricional', {
            'fields': ('info_nutricional',)
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion')
        }),
    )


@admin.register(RecetaIngrediente)
class RecetaIngredienteAdmin(admin.ModelAdmin):
    list_display = ['receta', 'ingrediente', 'cantidad', 'unidad_medida']
    list_filter = ['receta', 'ingrediente']
    search_fields = ['receta__nombre', 'ingrediente__nombre']
