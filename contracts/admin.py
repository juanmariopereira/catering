from django.contrib import admin
from django.utils.html import format_html

from .models import Contrato, PausaContrato, q_filtro_estado


class EstadoContratoListFilter(admin.SimpleListFilter):
    """Filtro por estado calculado del contrato."""
    title = 'Estado'
    parameter_name = 'estado_calc'

    def lookups(self, request, model_admin):
        return [
            ('activo', 'Activo'),
            ('pre_renovacion', 'Pre-Renovación'),
            ('pausado', 'Pausado'),
            ('vencido', 'Vencido'),
            ('cancelado', 'Cancelado'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'activo':
            return queryset.filter(q_filtro_estado('activo'))
        if self.value() == 'pre_renovacion':
            return queryset.filter(q_filtro_estado('pre_renovacion'))
        if self.value() == 'pausado':
            return queryset.filter(q_filtro_estado('pausado'))
        if self.value() == 'vencido':
            return queryset.filter(q_filtro_estado('vencido'))
        if self.value() == 'cancelado':
            return queryset.filter(q_filtro_estado('cancelado'))
        return queryset


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'plan', 'fecha_inicio', 'fecha_fin', 'precio', 'estado_badge', 'frecuencia_pago']
    list_filter = [EstadoContratoListFilter, 'frecuencia_pago', 'fecha_inicio', 'fecha_creacion']
    search_fields = ['cliente__nombre', 'plan__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'estado_display']
    date_hierarchy = 'fecha_inicio'
    fieldsets = (
        ('Información del Contrato', {
            'fields': ('cliente', 'plan', 'estado_display')
        }),
        ('Fechas', {
            'fields': ('fecha_inicio', 'fecha_fin', 'fecha_cancelacion')
        }),
        ('Precio y Pago', {
            'fields': ('precio', 'frecuencia_pago')
        }),
        ('Entrega', {
            'fields': ('direccion_entrega', 'link_maps', 'horario_entrega', 'dias_entrega')
        }),
        ('Pausa global', {
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
            'pre_renovacion': '#2196F3',
            'pausado': 'orange',
            'vencido': '#757575',
            'cancelado': 'red'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def estado_display(self, obj):
        """Estado calculado (solo lectura)."""
        return obj.get_estado_display()
    estado_display.short_description = 'Estado'

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


@admin.register(PausaContrato)
class PausaContratoAdmin(admin.ModelAdmin):
    list_display = ['contrato', 'fecha_inicio', 'fecha_fin', 'motivo', 'fecha_creacion']
    list_filter = ['fecha_inicio', 'fecha_fin']
    search_fields = ['contrato__cliente__nombre', 'motivo']
    date_hierarchy = 'fecha_inicio'
    autocomplete_fields = ['contrato']
