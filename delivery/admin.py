from django.contrib import admin
from .models import PuntoPartidaEntrega


@admin.register(PuntoPartidaEntrega)
class PuntoPartidaEntregaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'latitud', 'longitud', 'activo', 'fecha_actualizacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'direccion')
    fields = ('nombre', 'direccion', 'latitud', 'longitud', 'activo', 'fecha_actualizacion')
    readonly_fields = ('fecha_actualizacion',)
