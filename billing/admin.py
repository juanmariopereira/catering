from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Cobro, Pago


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    readonly_fields = ['fecha_creacion']


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ['numero_cobro', 'cliente', 'fecha_generacion', 'fecha_vencimiento', 'monto', 'estado_badge', 'monto_pagado_display']
    list_filter = ['estado', 'fecha_generacion', 'fecha_vencimiento']
    search_fields = ['numero_cobro', 'contrato__cliente__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'numero_cobro']
    date_hierarchy = 'periodo_hasta'
    inlines = [PagoInline]
    fieldsets = (
        ('Información del cobro', {
            'fields': ('numero_cobro', 'contrato', 'estado')
        }),
        ('Período y monto', {
            'fields': ('periodo_desde', 'periodo_hasta', 'monto')
        }),
        ('Fechas', {
            'fields': ('fecha_generacion', 'fecha_vencimiento')
        }),
        ('Información adicional', {
            'fields': ('notas', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )
    actions = ['actualizar_estados']

    def cliente(self, obj):
        return obj.contrato.cliente.nombre
    cliente.short_description = 'Cliente'

    def estado_badge(self, obj):
        colors = {
            'pendiente': 'orange',
            'pagada': 'green',
            'vencida': 'red'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def monto_pagado_display(self, obj):
        monto_pagado = obj.calcular_monto_pagado()
        return f'Bs. {monto_pagado:.2f} / Bs. {obj.monto:.2f}'
    monto_pagado_display.short_description = 'Monto pagado'

    def actualizar_estados(self, request, queryset):
        for cobro in queryset:
            cobro.actualizar_estado()
        self.message_user(request, f'{queryset.count()} cobro(s) actualizado(s).')
    actualizar_estados.short_description = 'Actualizar estados de cobros seleccionados'


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['cobro', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'fecha_creacion']
    list_filter = ['metodo_pago', 'fecha_pago', 'fecha_creacion']
    search_fields = ['cobro__numero_cobro', 'cobro__contrato__cliente__nombre', 'referencia']
    readonly_fields = ['fecha_creacion']
    date_hierarchy = 'fecha_pago'
