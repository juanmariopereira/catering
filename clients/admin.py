from django.contrib import admin
from .models import Cliente, IngredienteNoGustado


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'email', 'telefono', 'activo', 'fecha_creacion']
    list_filter = ['activo', 'fecha_creacion']
    search_fields = ['nombre', 'email', 'telefono']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'email', 'telefono', 'titular', 'activo')
        }),
        ('Dirección', {
            'fields': ('direccion', 'link_maps')
        }),
        ('Información Adicional', {
            'fields': ('notas', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )


@admin.register(IngredienteNoGustado)
class IngredienteNoGustadoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'ingrediente', 'fecha_agregado']
    list_filter = ['fecha_agregado', 'ingrediente']
    search_fields = ['cliente__nombre', 'ingrediente__nombre']
    readonly_fields = ['fecha_agregado']
