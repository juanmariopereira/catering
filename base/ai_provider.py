"""
Capa unificada de acceso a proveedores de IA.

Resuelve, para cada uso del sistema (acción), qué modelo/proveedor usar según la
configuración del admin (ProveedorIA / ModeloIA / AsignacionUsoIA), aplica los
límites de uso (tokens y solicitudes por minuto/día) y despacha la llamada al
SDK correcto:

- OpenAI, Gemini y Grok: SDK de OpenAI con el ``base_url`` del proveedor
  (Gemini y Grok exponen un endpoint compatible con la API de OpenAI).
- Anthropic (Claude): SDK ``anthropic``.

Las funciones de servicio (recetas, planning, dietas, contratos) llaman a
``completar_ia(...)`` en lugar de instanciar un cliente concreto.
"""
import logging
from datetime import timedelta
from typing import Dict, Optional, Tuple

from django.db.models import Sum
from django.utils import timezone

from base.ai_logging import extraer_usage, registrar_llamada_ia

logger = logging.getLogger(__name__)


class ConfiguracionIAError(Exception):
    """No hay un modelo/proveedor válido configurado para esta acción."""


class LimiteIAExcedido(Exception):
    """Se superó un límite de uso (tokens o solicitudes por minuto/día)."""


# base_url por proveedor para el SDK de OpenAI. None = endpoint propio de OpenAI.
BASE_URLS = {
    'openai': None,
    'grok': 'https://api.x.ai/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai/',
}

# max_tokens por defecto para la respuesta (Anthropic lo exige; en OpenAI-compat
# solo se envía si se especifica).
MAX_TOKENS_DEFECTO = 2000


def resolver_cadena(accion: str):
    """
    Devuelve la cadena de fallback (lista ordenada de ModeloIA) para la acción,
    incluyendo solo los modelos disponibles (nivel activo, modelo y proveedor
    habilitados y con clave API), por orden de prioridad ascendente.
    """
    from base.models import AsignacionUsoIA

    niveles = (
        AsignacionUsoIA.objects
        .filter(accion=accion, activo=True)
        .select_related('modelo', 'modelo__proveedor')
        .order_by('orden', 'id')
    )
    cadena = []
    for nivel in niveles:
        modelo = nivel.modelo
        if modelo and modelo.disponible and modelo not in cadena:
            cadena.append(modelo)
    return cadena


def verificar_limites(modelo) -> None:
    """
    Comprueba el uso reciente del modelo (a partir de AIRequestLog) contra sus
    límites. Un límite en 0 se considera "sin límite".

    Raises:
        LimiteIAExcedido: si se alcanzó o superó alguno de los límites.
    """
    from base.models import AIRequestLog

    ahora = timezone.now()
    hace_un_minuto = ahora - timedelta(minutes=1)
    hace_un_dia = ahora - timedelta(days=1)

    base_qs = AIRequestLog.objects.filter(modelo=modelo.modelo_id, exito=True)
    qs_min = base_qs.filter(fecha_hora__gte=hace_un_minuto)
    qs_dia = base_qs.filter(fecha_hora__gte=hace_un_dia)

    def _tokens(qs):
        return qs.aggregate(s=Sum('total_tokens'))['s'] or 0

    if modelo.requests_por_minuto and qs_min.count() >= modelo.requests_por_minuto:
        raise LimiteIAExcedido(
            f'Límite de {modelo.requests_por_minuto} solicitudes por minuto alcanzado '
            f'para "{modelo}". Inténtalo en unos segundos.'
        )
    if modelo.requests_por_dia and qs_dia.count() >= modelo.requests_por_dia:
        raise LimiteIAExcedido(
            f'Límite de {modelo.requests_por_dia} solicitudes por día alcanzado '
            f'para "{modelo}".'
        )
    if modelo.tokens_por_minuto and _tokens(qs_min) >= modelo.tokens_por_minuto:
        raise LimiteIAExcedido(
            f'Límite de {modelo.tokens_por_minuto} tokens por minuto alcanzado '
            f'para "{modelo}". Inténtalo en unos segundos.'
        )
    if modelo.tokens_por_dia and _tokens(qs_dia) >= modelo.tokens_por_dia:
        raise LimiteIAExcedido(
            f'Límite de {modelo.tokens_por_dia} tokens por día alcanzado para "{modelo}".'
        )


def _completar_openai_compat(modelo, system_prompt, user_prompt, json_mode, temperature, max_tokens) -> Tuple[str, Dict[str, int]]:
    """Llamada vía SDK de OpenAI (OpenAI, Gemini o Grok)."""
    from openai import OpenAI

    base_url = BASE_URLS.get(modelo.proveedor.codigo)
    kwargs_client = {'api_key': modelo.proveedor.api_key}
    if base_url:
        kwargs_client['base_url'] = base_url
    client = OpenAI(**kwargs_client)

    kwargs = {
        'model': modelo.modelo_id,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    if temperature is not None:
        kwargs['temperature'] = temperature
    if json_mode:
        kwargs['response_format'] = {'type': 'json_object'}
    if max_tokens:
        kwargs['max_tokens'] = max_tokens

    response = client.chat.completions.create(**kwargs)
    content = (response.choices[0].message.content or '') if response.choices else ''
    return content, extraer_usage(response)


def _completar_anthropic(modelo, system_prompt, user_prompt, json_mode, max_tokens) -> Tuple[str, Dict[str, int]]:
    """Llamada vía SDK de Anthropic (Claude)."""
    import anthropic

    client = anthropic.Anthropic(api_key=modelo.proveedor.api_key)
    system = system_prompt
    if json_mode:
        system = (system_prompt or '') + (
            '\n\nResponde ÚNICAMENTE con un JSON válido, sin texto adicional, '
            'sin explicaciones y sin envolverlo en ```.'
        )
    response = client.messages.create(
        model=modelo.modelo_id,
        max_tokens=max_tokens or MAX_TOKENS_DEFECTO,
        system=system,
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    partes = [getattr(b, 'text', '') for b in response.content if getattr(b, 'type', None) == 'text']
    content = ''.join(partes).strip()
    usage = getattr(response, 'usage', None)
    prompt_tokens = getattr(usage, 'input_tokens', 0) if usage else 0
    completion_tokens = getattr(usage, 'output_tokens', 0) if usage else 0
    return content, {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': prompt_tokens + completion_tokens,
    }


def _despachar(modelo, system_prompt, user_prompt, json_mode, temperature, max_tokens) -> Tuple[str, Dict[str, int]]:
    """Despacha la llamada al SDK adecuado según el proveedor del modelo."""
    if modelo.proveedor.codigo == 'anthropic':
        return _completar_anthropic(modelo, system_prompt, user_prompt, json_mode, max_tokens)
    # Anthropic no admite temperature en los modelos recientes; el resto sí.
    return _completar_openai_compat(modelo, system_prompt, user_prompt, json_mode, temperature, max_tokens)


def completar_ia(
    accion: str,
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = False,
    temperature: Optional[float] = 0.4,
    max_tokens: Optional[int] = None,
    request=None,
    objeto_tipo: str = '',
    objeto_id: Optional[int] = None,
) -> str:
    """
    Ejecuta una llamada de IA para la acción dada, resolviendo el modelo
    asignado, aplicando límites y registrando el uso (tokens) en AIRequestLog.

    Args:
        accion: clave de AIRequestLog.ACCION_CHOICES (ej. 'sugerir_menu').
        system_prompt / user_prompt: mensajes.
        json_mode: si la respuesta debe ser un JSON.
        temperature: temperatura (se ignora en proveedores que no la admiten).
        max_tokens: máximo de tokens de salida.
        request / objeto_tipo / objeto_id: metadatos para el log.

    Recorre la cadena de fallback configurada para la acción: usa el modelo de
    mayor prioridad disponible y, si falla, no está disponible o supera su
    límite, pasa al siguiente modelo de la jerarquía.

    Returns:
        El texto de la respuesta del primer modelo que responde correctamente.

    Raises:
        ConfiguracionIAError: si no hay ningún modelo disponible para la acción.
        LimiteIAExcedido / Exception: si TODOS los modelos de la cadena fallan
            (se relanza el último error encontrado).
    """
    cadena = resolver_cadena(accion)
    if not cadena:
        raise ConfiguracionIAError(
            f'No hay ningún modelo de IA disponible para "{accion}". '
            'Revisa las asignaciones de uso de IA y que el proveedor esté '
            'habilitado y con clave API en el panel de administración.'
        )

    usuario = getattr(request, 'user', None) if request else None
    ultimo_error = None

    for modelo in cadena:
        # Límite de uso: si está excedido, se omite este modelo y se prueba el siguiente.
        try:
            verificar_limites(modelo)
        except LimiteIAExcedido as e:
            ultimo_error = e
            logger.warning('Modelo %s omitido por límite de uso; probando siguiente. (%s)', modelo.modelo_id, e)
            continue

        try:
            content, usage = _despachar(modelo, system_prompt, user_prompt, json_mode, temperature, max_tokens)
        except Exception as e:
            ultimo_error = e
            registrar_llamada_ia(
                accion=accion,
                modelo=modelo.modelo_id,
                exito=False,
                mensaje_error=str(e),
                objeto_tipo=objeto_tipo,
                objeto_id=objeto_id,
                usuario=usuario,
            )
            logger.warning('Modelo %s falló para "%s"; probando siguiente de la cadena. (%s)', modelo.modelo_id, accion, e)
            continue

        registrar_llamada_ia(
            accion=accion,
            modelo=modelo.modelo_id,
            objeto_tipo=objeto_tipo,
            objeto_id=objeto_id,
            usuario=usuario,
            **usage,
        )
        return content

    # Ningún modelo de la cadena funcionó: se relanza el último error.
    if ultimo_error is not None:
        raise ultimo_error
    raise ConfiguracionIAError(f'No se pudo completar la acción "{accion}" con ningún modelo disponible.')


def ia_disponible() -> bool:
    """True si hay al menos un proveedor habilitado con clave API."""
    from base.models import ProveedorIA

    try:
        return ProveedorIA.objects.filter(activo=True).exclude(api_key='').exists()
    except Exception:
        return False
