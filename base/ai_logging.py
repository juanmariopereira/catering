"""
Utilidad para registrar llamadas a la API de IA.
"""
import threading
from typing import Dict, Optional

# Acumulador de tokens por petición (request). El middleware lo reinicia al
# inicio de cada request y lo lee al final para mostrar al usuario cuántos
# tokens consumió la IA en esa interacción.
_token_usage_local = threading.local()


def reset_token_usage() -> None:
    """Reinicia el acumulador de tokens de IA para la petición actual."""
    _token_usage_local.data = {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
        'llamadas': 0,
    }


def _acumular_token_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
    """Suma el uso de tokens de una llamada al acumulador de la petición."""
    data = getattr(_token_usage_local, 'data', None)
    if data is None:
        reset_token_usage()
        data = _token_usage_local.data
    data['prompt_tokens'] += prompt_tokens or 0
    data['completion_tokens'] += completion_tokens or 0
    data['total_tokens'] += total_tokens or 0
    data['llamadas'] += 1


def get_token_usage() -> Optional[Dict[str, int]]:
    """Devuelve el uso de tokens acumulado en la petición actual (o None)."""
    return getattr(_token_usage_local, 'data', None)


def registrar_llamada_ia(
    accion: str,
    modelo: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    exito: bool = True,
    mensaje_error: str = '',
    objeto_tipo: str = '',
    objeto_id: Optional[int] = None,
    usuario=None,
) -> None:
    """
    Registra una llamada a la API de IA en la tabla AIRequestLog.

    Args:
        accion: Una de las claves en AIRequestLog.ACCION_CHOICES
        modelo: Modelo usado (ej. gpt-4o-mini)
        prompt_tokens: Tokens de entrada (prompt)
        completion_tokens: Tokens de salida (respuesta)
        total_tokens: Total de tokens
        exito: Si la llamada fue exitosa
        mensaje_error: Mensaje si falló
        objeto_tipo: Tipo de objeto relacionado ('receta', 'ingrediente', 'plan')
        objeto_id: ID del objeto
        usuario: Usuario que realizó la acción (opcional)
    """
    total_efectivo = total_tokens or (prompt_tokens + completion_tokens)
    # Acumular en la petición actual aunque falle el guardado en BD, para poder
    # mostrar el consumo al usuario.
    _acumular_token_usage(prompt_tokens, completion_tokens, total_efectivo)
    try:
        from base.models import AIRequestLog

        AIRequestLog.objects.create(
            accion=accion,
            modelo=modelo or 'gpt-4o-mini',
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total_efectivo,
            exito=exito,
            mensaje_error=mensaje_error[:2000] if mensaje_error else '',
            objeto_tipo=objeto_tipo or '',
            objeto_id=objeto_id,
            usuario=usuario,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('No se pudo registrar log de IA: %s', e)


def extraer_usage(response) -> Dict[str, int]:
    """Extrae prompt_tokens, completion_tokens y total_tokens de una respuesta de OpenAI."""
    usage = getattr(response, 'usage', None)
    if not usage:
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    prompt = getattr(usage, 'prompt_tokens', 0) or getattr(usage, 'input_tokens', 0)
    completion = getattr(usage, 'completion_tokens', 0) or getattr(usage, 'output_tokens', 0)
    total = getattr(usage, 'total_tokens', 0) or (prompt + completion)
    return {
        'prompt_tokens': prompt,
        'completion_tokens': completion,
        'total_tokens': total,
    }
