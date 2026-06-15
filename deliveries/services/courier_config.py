"""
Resolución de la configuración de seguimiento del repartidor.

Combina la configuración a nivel de sistema (base.ParametroSistema) con el
override por entregador (routes.Entregador). Devuelve la config efectiva que
consume la app móvil y que el backend usa para el check-in automático.
"""

# Valores por defecto del sistema (se usan si no hay ParametroSistema ni override).
DEFAULTS = {
    'auto_checkin': False,
    'radio_metros': 150,
    'ping_segundos': 5,
}

# Claves en ParametroSistema para la config a nivel de sistema.
CLAVE_AUTO = 'checkin_auto'
CLAVE_RADIO = 'checkin_radio_metros'
CLAVE_PING = 'ping_intervalo_segundos'


def _get_param(clave):
    from base.models import ParametroSistema
    p = ParametroSistema.objects.filter(clave=clave).first()
    return (p.valor.strip() if p and p.valor else '') or None


def _to_bool(valor, defecto):
    if valor is None:
        return defecto
    return str(valor).strip().lower() in ('1', 'true', 'si', 'sí', 'yes', 'on')


def _to_int(valor, defecto, minimo=1):
    try:
        v = int(str(valor).strip())
        return v if v >= minimo else defecto
    except (TypeError, ValueError):
        return defecto


def config_sistema():
    """Configuración a nivel de sistema (ParametroSistema con defaults)."""
    return {
        'auto_checkin': _to_bool(_get_param(CLAVE_AUTO), DEFAULTS['auto_checkin']),
        'radio_metros': _to_int(_get_param(CLAVE_RADIO), DEFAULTS['radio_metros']),
        'ping_segundos': _to_int(_get_param(CLAVE_PING), DEFAULTS['ping_segundos']),
    }


def resolver_config(entregador=None):
    """
    Configuración efectiva para un entregador: parte de la del sistema y aplica
    el override del entregador en los campos que no sean None.

    Returns dict: {auto_checkin: bool, radio_metros: int, ping_segundos: int}.
    """
    cfg = config_sistema()
    if entregador is not None:
        if entregador.checkin_auto is not None:
            cfg['auto_checkin'] = bool(entregador.checkin_auto)
        if entregador.checkin_radio_metros is not None:
            cfg['radio_metros'] = _to_int(entregador.checkin_radio_metros, cfg['radio_metros'])
        if entregador.ping_intervalo_segundos is not None:
            cfg['ping_segundos'] = _to_int(entregador.ping_intervalo_segundos, cfg['ping_segundos'])
    return cfg


def radio_km(entregador=None):
    """Radio de aproximación efectivo en km (para is_near_stop)."""
    return resolver_config(entregador)['radio_metros'] / 1000.0
