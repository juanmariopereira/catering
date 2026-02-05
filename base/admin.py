from django.contrib import admin
from .models import AIRequestLog


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'accion', 'modelo', 'total_tokens', 'prompt_tokens', 'completion_tokens', 'exito', 'usuario')
    list_filter = ('accion', 'exito', 'modelo')
    search_fields = ('accion', 'mensaje_error')
    readonly_fields = ('fecha_hora', 'accion', 'modelo', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'exito', 'mensaje_error', 'objeto_tipo', 'objeto_id', 'usuario')
    date_hierarchy = 'fecha_hora'
