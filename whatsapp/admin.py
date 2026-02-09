from django.contrib import admin
from .models import Reclamo


@admin.register(Reclamo)
class ReclamoAdmin(admin.ModelAdmin):
    list_display = ('telefono_whatsapp', 'cliente', 'tipo', 'leido', 'respondido', 'fecha_recibido')
    list_filter = ('tipo', 'leido', 'respondido')
    search_fields = ('mensaje', 'telefono_whatsapp', 'cliente__nombre')
    readonly_fields = ('mensaje_id_whatsapp', 'fecha_recibido', 'created_at', 'updated_at')
    raw_id_fields = ('cliente',)
