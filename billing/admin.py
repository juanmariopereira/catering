from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Factura, Pago


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    readonly_fields = ['fecha_creacion']


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ['numero_factura', 'cliente', 'fecha_emision', 'fecha_vencimiento', 'monto', 'estado_badge', 'monto_pagado_display']
    list_filter = ['estado', 'fecha_emision', 'fecha_vencimiento']
    search_fields = ['numero_factura', 'contrato__cliente__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'numero_factura']
    date_hierarchy = 'fecha_emision'
    inlines = [PagoInline]
    fieldsets = (
        ('Información de Factura', {
            'fields': ('numero_factura', 'contrato', 'estado')
        }),
        ('Fechas', {
            'fields': ('fecha_emision', 'fecha_vencimiento', 'periodo_desde', 'periodo_hasta')
        }),
        ('Monto', {
            'fields': ('monto',)
        }),
        ('Información Adicional', {
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
        return f'${monto_pagado:.2f} / ${obj.monto:.2f}'
    monto_pagado_display.short_description = 'Monto Pagado'

    def actualizar_estados(self, request, queryset):
        for factura in queryset:
            factura.actualizar_estado()
        self.message_user(request, f'{queryset.count()} factura(s) actualizada(s).')
    actualizar_estados.short_description = 'Actualizar estados de facturas seleccionadas'


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['factura', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'fecha_creacion']
    list_filter = ['metodo_pago', 'fecha_pago', 'fecha_creacion']
    search_fields = ['factura__numero_factura', 'factura__contrato__cliente__nombre', 'referencia']
    readonly_fields = ['fecha_creacion']
    date_hierarchy = 'fecha_pago'
