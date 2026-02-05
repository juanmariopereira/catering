from django.contrib import admin
from django.utils.html import format_html
from .models import Contrato


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'plan', 'fecha_inicio', 'fecha_fin', 'precio', 'estado_badge', 'frecuencia_pago']
    list_filter = ['estado', 'frecuencia_pago', 'fecha_inicio', 'fecha_creacion']
    search_fields = ['cliente__nombre', 'plan__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha_inicio'
    fieldsets = (
        ('Información del Contrato', {
            'fields': ('cliente', 'plan', 'estado')
        }),
        ('Fechas', {
            'fields': ('fecha_inicio', 'fecha_fin')
        }),
        ('Precio y Pago', {
            'fields': ('precio', 'frecuencia_pago')
        }),
        ('Entrega', {
            'fields': ('direccion_entrega', 'horario_entrega', 'dias_entrega')
        }),
        ('Pausa', {
            'fields': ('fecha_pausa', 'fecha_reanudacion'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('notas', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )
    actions = ['pausar_contratos', 'reanudar_contratos', 'cancelar_contratos']

    def estado_badge(self, obj):
        colors = {
            'activo': 'green',
            'pausado': 'orange',
            'cancelado': 'red'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def pausar_contratos(self, request, queryset):
        for contrato in queryset:
            contrato.pausar()
        self.message_user(request, f'{queryset.count()} contrato(s) pausado(s).')
    pausar_contratos.short_description = 'Pausar contratos seleccionados'

    def reanudar_contratos(self, request, queryset):
        for contrato in queryset:
            contrato.reanudar()
        self.message_user(request, f'{queryset.count()} contrato(s) reanudado(s).')
    reanudar_contratos.short_description = 'Reanudar contratos seleccionados'

    def cancelar_contratos(self, request, queryset):
        for contrato in queryset:
            contrato.cancelar()
        self.message_user(request, f'{queryset.count()} contrato(s) cancelado(s).')
    cancelar_contratos.short_description = 'Cancelar contratos seleccionados'
