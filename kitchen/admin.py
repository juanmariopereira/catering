from django.contrib import admin
from .models import DetalleCocina


@admin.register(DetalleCocina)
class DetalleCocinaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'fecha_creacion', 'fecha_actualizacion']
    list_filter = ['fecha', 'fecha_creacion']
    date_hierarchy = 'fecha'
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    search_fields = ['notas']
