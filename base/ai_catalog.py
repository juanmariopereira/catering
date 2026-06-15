"""
Catálogo de modelos de IA conocidos y sus límites de uso por defecto.

Estos valores son un punto de partida razonable por modelo; los límites reales
dependen del nivel/tier de tu cuenta en cada proveedor, así que son editables.
La UI de configuración los usa para autocompletar los límites al seleccionar un
modelo, y ModeloIA los aplica como defaults dinámicos al crear un modelo nuevo.
"""

LIMIT_KEYS = ('tokens_por_minuto', 'tokens_por_dia', 'requests_por_minuto', 'requests_por_dia')

# Límites genéricos (coinciden con los defaults del campo en el modelo). Sirven
# de respaldo cuando no hay datos del modelo ni del proveedor.
DEFAULTS_GENERICOS = {
    'tokens_por_minuto': 100000,
    'tokens_por_dia': 2000000,
    'requests_por_minuto': 60,
    'requests_por_dia': 5000,
}

# Respaldo por proveedor para modelos no catalogados.
DEFAULTS_POR_PROVEEDOR = {
    'openai':    {'tokens_por_minuto': 200000,  'tokens_por_dia': 10000000, 'requests_por_minuto': 500,  'requests_por_dia': 10000},
    'anthropic': {'tokens_por_minuto': 40000,   'tokens_por_dia': 1000000,  'requests_por_minuto': 50,   'requests_por_dia': 5000},
    'gemini':    {'tokens_por_minuto': 1000000, 'tokens_por_dia': 50000000, 'requests_por_minuto': 1000, 'requests_por_dia': 50000},
    'grok':      {'tokens_por_minuto': 100000,  'tokens_por_dia': 2000000,  'requests_por_minuto': 60,   'requests_por_dia': 5000},
}

# Modelos conocidos: modelo_id -> {proveedor, nombre, límites...}
MODELOS_CONOCIDOS = {
    # OpenAI
    'gpt-4o-mini': {'proveedor': 'openai', 'nombre': 'OpenAI · GPT-4o mini',
                    'tokens_por_minuto': 200000, 'tokens_por_dia': 10000000, 'requests_por_minuto': 500, 'requests_por_dia': 10000},
    'gpt-4o': {'proveedor': 'openai', 'nombre': 'OpenAI · GPT-4o',
               'tokens_por_minuto': 30000, 'tokens_por_dia': 1000000, 'requests_por_minuto': 500, 'requests_por_dia': 10000},
    'gpt-4.1-mini': {'proveedor': 'openai', 'nombre': 'OpenAI · GPT-4.1 mini',
                     'tokens_por_minuto': 200000, 'tokens_por_dia': 10000000, 'requests_por_minuto': 500, 'requests_por_dia': 10000},
    'gpt-4.1': {'proveedor': 'openai', 'nombre': 'OpenAI · GPT-4.1',
                'tokens_por_minuto': 30000, 'tokens_por_dia': 1000000, 'requests_por_minuto': 500, 'requests_por_dia': 10000},
    # Anthropic (Claude)
    'claude-opus-4-8': {'proveedor': 'anthropic', 'nombre': 'Claude Opus 4.8',
                        'tokens_por_minuto': 40000, 'tokens_por_dia': 1000000, 'requests_por_minuto': 50, 'requests_por_dia': 5000},
    'claude-sonnet-4-6': {'proveedor': 'anthropic', 'nombre': 'Claude Sonnet 4.6',
                          'tokens_por_minuto': 80000, 'tokens_por_dia': 2000000, 'requests_por_minuto': 50, 'requests_por_dia': 5000},
    'claude-haiku-4-5': {'proveedor': 'anthropic', 'nombre': 'Claude Haiku 4.5',
                         'tokens_por_minuto': 100000, 'tokens_por_dia': 2500000, 'requests_por_minuto': 50, 'requests_por_dia': 5000},
    # Google Gemini
    'gemini-2.0-flash': {'proveedor': 'gemini', 'nombre': 'Gemini 2.0 Flash',
                         'tokens_por_minuto': 1000000, 'tokens_por_dia': 50000000, 'requests_por_minuto': 2000, 'requests_por_dia': 50000},
    'gemini-1.5-pro': {'proveedor': 'gemini', 'nombre': 'Gemini 1.5 Pro',
                       'tokens_por_minuto': 2000000, 'tokens_por_dia': 50000000, 'requests_por_minuto': 1000, 'requests_por_dia': 50000},
    'gemini-1.5-flash': {'proveedor': 'gemini', 'nombre': 'Gemini 1.5 Flash',
                         'tokens_por_minuto': 1000000, 'tokens_por_dia': 50000000, 'requests_por_minuto': 2000, 'requests_por_dia': 50000},
    # xAI Grok
    'grok-2-latest': {'proveedor': 'grok', 'nombre': 'Grok 2',
                      'tokens_por_minuto': 100000, 'tokens_por_dia': 2000000, 'requests_por_minuto': 60, 'requests_por_dia': 5000},
    'grok-beta': {'proveedor': 'grok', 'nombre': 'Grok Beta',
                  'tokens_por_minuto': 100000, 'tokens_por_dia': 2000000, 'requests_por_minuto': 60, 'requests_por_dia': 5000},
}


def defaults_para(modelo_id, codigo_proveedor=None):
    """Devuelve los 4 límites por defecto recomendados para un modelo.

    Prioridad: datos del modelo catalogado → respaldo por proveedor → genérico.
    """
    info = MODELOS_CONOCIDOS.get((modelo_id or '').strip())
    if info:
        return {k: info[k] for k in LIMIT_KEYS}
    if codigo_proveedor in DEFAULTS_POR_PROVEEDOR:
        return dict(DEFAULTS_POR_PROVEEDOR[codigo_proveedor])
    return dict(DEFAULTS_GENERICOS)


def nombre_sugerido(modelo_id):
    """Nombre visible sugerido para un modelo catalogado (o '')."""
    info = MODELOS_CONOCIDOS.get((modelo_id or '').strip())
    return info['nombre'] if info else ''


def catalogo_para_select():
    """
    Lista para poblar el <select> de modelos conocidos, agrupada por proveedor:
    [{'codigo': 'openai', 'modelos': [{'modelo_id', 'nombre', 'tokens_por_minuto', ...}, ...]}, ...]
    """
    from base.models import ProveedorIA

    nombres_prov = dict(ProveedorIA.CODIGO_CHOICES)
    grupos = {}
    for modelo_id, info in MODELOS_CONOCIDOS.items():
        cod = info['proveedor']
        grupos.setdefault(cod, []).append({
            'modelo_id': modelo_id,
            'nombre': info['nombre'],
            **{k: info[k] for k in LIMIT_KEYS},
        })
    return [
        {'codigo': cod, 'nombre': nombres_prov.get(cod, cod), 'modelos': grupos[cod]}
        for cod in ('openai', 'anthropic', 'gemini', 'grok') if cod in grupos
    ]
