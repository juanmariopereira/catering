from django.contrib import admin
from .models import Entregador, Ruta, RutaCliente, HistoricoAsignacionEntrega


@admin.register(Entregador)
class EntregadorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'vehiculo', 'activo', 'fecha_creacion']
    list_filter = ['activo', 'fecha_creacion']
    search_fields = ['nombre', 'telefono', 'vehiculo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']


class RutaClienteInline(admin.TabularInline):
    model = RutaCliente
    extra = 1
    ordering = ['orden_entrega']


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'entregador', 'activa', 'total_clientes', 'fecha_creacion']
    list_filter = ['activa', 'fecha', 'entregador', 'fecha_creacion']
    search_fields = ['entregador__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha'
    inlines = [RutaClienteInline]

    def total_clientes(self, obj):
        return obj.ruta_clientes.count()
    total_clientes.short_description = 'Total Clientes'


@admin.register(RutaCliente)
class RutaClienteAdmin(admin.ModelAdmin):
    list_display = ['ruta', 'contrato', 'orden_entrega']
    list_filter = ['ruta', 'ruta__fecha']
    search_fields = ['contrato__cliente__nombre', 'ruta__entregador__nombre']
    ordering = ['ruta', 'orden_entrega']


@admin.register(HistoricoAsignacionEntrega)
class HistoricoAsignacionEntregaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'entregador', 'contrato', 'planificacion_menu', 'created_at']
    list_filter = ['fecha', 'entregador']
    search_fields = ['contrato__cliente__nombre', 'entregador__nombre']
    readonly_fields = ['created_at']
    date_hierarchy = 'fecha'
    ordering = ['-fecha', 'entregador', 'contrato']
