from django.contrib import admin
from django.db.models import Min, Value
from django.db.models.functions import Coalesce
from .models import TipoReceta, TipoIngrediente, UnidadMedida, Alergeno, Ingrediente, Receta, RecetaIngrediente


@admin.register(TipoIngrediente)
class TipoIngredienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre']
    ordering = ['orden', 'nombre']


@admin.register(Alergeno)
class AlergenoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre']
    ordering = ['orden', 'nombre']


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo', 'tipo', 'orden', 'activo', 'fecha_creacion']
    list_filter = ['activo', 'tipo']
    search_fields = ['nombre', 'simbolo']
    ordering = ['orden', 'nombre']


@admin.register(TipoReceta)
class TipoRecetaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre']
    ordering = ['orden', 'nombre']


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo_ingrediente', 'unidad_medida', 'activo', 'fecha_creacion']
    list_filter = ['activo', 'tipo_ingrediente', 'unidad_medida', 'fecha_creacion']
    search_fields = ['nombre']
    readonly_fields = ['fecha_creacion']


class RecetaIngredienteInline(admin.TabularInline):
    model = RecetaIngrediente
    extra = 1


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activa', 'producido_en_cocina', 'fecha_creacion']
    list_filter = ['activa', 'producido_en_cocina', 'tipos_receta', 'momentos_dia', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    filter_horizontal = ['tipos_receta', 'momentos_dia']
    inlines = [RecetaIngredienteInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _orden_tipo=Coalesce(Min('tipos_receta__nombre'), Value('')),
            _orden_momento=Coalesce(Min('momentos_dia__nombre'), Value('')),
        ).order_by('nombre', '_orden_tipo', '_orden_momento', 'producido_en_cocina')
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'tipos_receta', 'momentos_dia', 'activa', 'producido_en_cocina')
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
