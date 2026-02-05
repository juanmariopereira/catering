from django.contrib import admin
from .models import PrevisionCompra, PrevisionCompraItem


class PrevisionCompraItemInline(admin.TabularInline):
    model = PrevisionCompraItem
    extra = 0
    readonly_fields = ['ingrediente', 'cantidad_total', 'unidad_medida']


@admin.register(PrevisionCompra)
class PrevisionCompraAdmin(admin.ModelAdmin):
    list_display = ['fecha_generacion', 'fecha_desde', 'fecha_hasta', 'total_items']
    list_filter = ['fecha_generacion', 'fecha_desde', 'fecha_hasta']
    readonly_fields = ['fecha_generacion']
    date_hierarchy = 'fecha_generacion'
    inlines = [PrevisionCompraItemInline]
    fieldsets = (
        ('Período', {
            'fields': ('fecha_desde', 'fecha_hasta')
        }),
        ('Información', {
            'fields': ('notas', 'fecha_generacion')
        }),
    )
    actions = ['recalcular_items']

    def total_items(self, obj):
        return obj.items.count()
    total_items.short_description = 'Total Items'

    def recalcular_items(self, request, queryset):
        for prevision in queryset:
            prevision.calcular_items()
        self.message_user(request, f'{queryset.count()} previsión(es) recalculada(s).')
    recalcular_items.short_description = 'Recalcular items de previsiones seleccionadas'


@admin.register(PrevisionCompraItem)
class PrevisionCompraItemAdmin(admin.ModelAdmin):
    list_display = ['prevision', 'ingrediente', 'cantidad_total', 'unidad_medida']
    list_filter = ['prevision', 'ingrediente']
    search_fields = ['ingrediente__nombre', 'prevision__fecha_desde']
