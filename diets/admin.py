from django.contrib import admin
from .models import Dieta, DietaReceta, TipoComida


@admin.register(TipoComida)
class TipoComidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'descripcion']
    ordering = ['orden']


class DietaRecetaInline(admin.TabularInline):
    model = DietaReceta
    extra = 1
    ordering = ['tipo_comida', 'orden']


@admin.register(Dieta)
class DietaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'mostrar_planes', 'activa', 'fecha_creacion']
    filter_horizontal = ['planes']

    def mostrar_planes(self, obj):
        return ", ".join(p.nombre for p in obj.planes.all()) or "—"
    mostrar_planes.short_description = "Planes"
    list_filter = ['activa', 'planes', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    inlines = [DietaRecetaInline]
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'planes', 'activa')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion')
        }),
    )


@admin.register(DietaReceta)
class DietaRecetaAdmin(admin.ModelAdmin):
    list_display = ['dieta', 'tipo_comida', 'receta', 'orden']
    list_filter = ['dieta', 'tipo_comida', 'receta']
    search_fields = ['dieta__nombre', 'receta__nombre']
    ordering = ['dieta', 'tipo_comida', 'orden']
