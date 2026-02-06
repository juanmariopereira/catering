from django.contrib import admin
from .models import AIRequestLog, ExternalApiRequestLog, Feriado, ParametroSistema, UserActionLog


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'nombre')
    list_filter = ('fecha',)
    search_fields = ('nombre',)
    date_hierarchy = 'fecha'


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'accion', 'modelo', 'total_tokens', 'prompt_tokens', 'completion_tokens', 'exito', 'usuario')
    list_filter = ('accion', 'exito', 'modelo')
    search_fields = ('accion', 'mensaje_error')
    readonly_fields = ('fecha_hora', 'accion', 'modelo', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'exito', 'mensaje_error', 'objeto_tipo', 'objeto_id', 'usuario')
    date_hierarchy = 'fecha_hora'


@admin.register(ParametroSistema)
class ParametroSistemaAdmin(admin.ModelAdmin):
    list_display = ('clave', 'valor_preview', 'descripcion')
    search_fields = ('clave', 'descripcion', 'valor')
    ordering = ('clave',)

    def valor_preview(self, obj):
        v = (obj.valor or '')[:60]
        return f'{v}…' if len(obj.valor or '') > 60 else v
    valor_preview.short_description = 'Valor'


@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'usuario', 'accion', 'modelo', 'objeto_repr_short')
    list_filter = ('accion', 'modelo')
    search_fields = ('modelo', 'objeto_repr', 'descripcion')
    readonly_fields = ('usuario', 'fecha_hora', 'accion', 'modelo', 'objeto_id', 'objeto_repr', 'descripcion', 'cambios')
    date_hierarchy = 'fecha_hora'

    def objeto_repr_short(self, obj):
        return (obj.objeto_repr or '')[:50]
    objeto_repr_short.short_description = 'Objeto'


@admin.register(ExternalApiRequestLog)
class ExternalApiRequestLogAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'api', 'response_status', 'exito', 'duracion_ms', 'objeto_tipo', 'objeto_id', 'usuario')
    list_filter = ('api', 'exito', 'response_status')
    search_fields = ('api', 'mensaje_error', 'response_status')
    readonly_fields = (
        'fecha_hora', 'api', 'endpoint', 'request_params', 'request_extra',
        'response_status', 'response_body', 'exito', 'mensaje_error',
        'duracion_ms', 'objeto_tipo', 'objeto_id', 'usuario',
    )
    date_hierarchy = 'fecha_hora'
