"""
Utilidad para registrar llamadas a la API de IA.
"""


def registrar_llamada_ia(
    accion: str,
    modelo: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    exito: bool = True,
    mensaje_error: str = '',
    objeto_tipo: str = '',
    objeto_id: int | None = None,
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
    try:
        from base.models import AIRequestLog

        AIRequestLog.objects.create(
            accion=accion,
            modelo=modelo or 'gpt-4o-mini',
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total_tokens or (prompt_tokens + completion_tokens),
            exito=exito,
            mensaje_error=mensaje_error[:2000] if mensaje_error else '',
            objeto_tipo=objeto_tipo or '',
            objeto_id=objeto_id,
            usuario=usuario,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('No se pudo registrar log de IA: %s', e)


def extraer_usage(response) -> dict[str, int]:
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
