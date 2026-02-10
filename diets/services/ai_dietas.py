"""
Servicio de sugerencia de dietas personalizadas con IA.

Propone combinaciones de recetas según objetivos nutricionales
(adelgazamiento, ganancia muscular, mantenimiento, etc.).
"""
import json
import logging
from typing import Any, Dict, List

from django.conf import settings

from base.ai_logging import extraer_usage, registrar_llamada_ia

logger = logging.getLogger(__name__)

OBJETIVOS_VALIDOS = [
    'adelgazamiento',
    'ganancia_muscular',
    'mantenimiento',
    'bajo_carbohidrato',
    'alta_proteina',
    'equilibrado',
]


def _get_openai_client():
    from openai import OpenAI
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise ValueError('OPENAI_API_KEY no está configurada.')
    return OpenAI(api_key=api_key)


def _build_context(plan_id=None):
    """Construye contexto: tipos de comida, recetas disponibles por momento."""
    from diets.models import TipoComida
    from recipes.models import Receta

    tipos_comida = list(
        TipoComida.objects.order_by('orden', 'nombre').values('id', 'nombre', 'orden')
    )

    recetas = []
    for r in Receta.objects.filter(activa=True).prefetch_related('momentos_dia').order_by('nombre'):
        momentos = [m.nombre for m in r.momentos_dia.all()]
        recetas.append({'id': r.id, 'nombre': r.nombre, 'momentos_aptos': momentos})

    plan_nombre = None
    if plan_id:
        from plans.models import Plan
        try:
            plan = Plan.objects.get(pk=plan_id)
            plan_nombre = plan.nombre
        except Plan.DoesNotExist:
            pass

    return {
        'tipos_comida': tipos_comida,
        'recetas': recetas,
        'plan_nombre': plan_nombre,
    }


def sugerir_dieta_personalizada(objetivo: str, plan_id: int = None, request=None) -> List[Dict[str, Any]]:
    """
    Sugiere una dieta personalizada según el objetivo.

    Args:
        objetivo: adelgazamiento, ganancia_muscular, mantenimiento, etc.
        plan_id: opcional, para considerar recetas típicas del plan

    Returns:
        Lista de dicts: [{"tipo_comida_id": int, "receta_id": int, "orden": int}, ...]
    """
    if objetivo not in OBJETIVOS_VALIDOS:
        objetivo = 'equilibrado'

    client = _get_openai_client()
    ctx = _build_context(plan_id)

    objetivos_desc = {
        'adelgazamiento': 'déficit calórico moderado, alta proteína, evitar excesos de carbohidratos',
        'ganancia_muscular': 'superávit calórico moderado, alta proteína, carbohidratos para energía',
        'mantenimiento': 'equilibrio calórico, variedad',
        'bajo_carbohidrato': 'reducir carbohidratos, aumentar grasas saludables y proteínas',
        'alta_proteina': 'priorizar proteínas en cada comida',
        'equilibrado': 'dieta variada y equilibrada',
    }

    system_prompt = """Eres un nutricionista experto. Sugieres combinaciones de recetas para un menú diario
según el objetivo nutricional. Solo usas recetas de la lista proporcionada (id y nombre).
Responde ÚNICAMENTE con un JSON: {"recetas": [{"tipo_comida_id": N, "receta_id": N, "orden": N}, ...]}
Asigna recetas apropiadas para cada momento del día. Usa "momentos_aptos" de cada receta.
Incluye variedad: desayuno, media mañana, comida, merienda, cena. Varias recetas por momento si corresponde."""

    user_prompt = f"""Objetivo: {objetivo} ({objetivos_desc.get(objetivo, objetivo)})
{f'Plan: {ctx["plan_nombre"]}' if ctx['plan_nombre'] else ''}

Tipos de comida:
{json.dumps(ctx['tipos_comida'], ensure_ascii=False)}

Recetas disponibles (id, nombre, momentos_aptos):
{json.dumps(ctx['recetas'], ensure_ascii=False)}

Genera un menú diario sugerido. Responde solo el JSON con clave "recetas"."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.6,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='sugerir_dieta',
            modelo='gpt-4o-mini',
            objeto_tipo='plan',
            objeto_id=plan_id,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return []

        data = json.loads(content)
        items = data.get('recetas', data.get('menu', data.get('items', [])))
        if not isinstance(items, list):
            return []

        tipo_ids = {t['id'] for t in ctx['tipos_comida']}
        receta_ids = {r['id'] for r in ctx['recetas']}
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tc_id = item.get('tipo_comida_id')
            rec_id = item.get('receta_id')
            try:
                tc_id = int(tc_id)
                rec_id = int(rec_id)
            except (TypeError, ValueError):
                continue
            if tc_id in tipo_ids and rec_id in receta_ids:
                result.append({
                    'tipo_comida_id': tc_id,
                    'receta_id': rec_id,
                    'orden': item.get('orden', 1),
                })
        return result

    except Exception as e:
        registrar_llamada_ia(
            accion='sugerir_dieta',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='plan',
            objeto_id=plan_id,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.exception('Error al sugerir dieta: %s', e)
        raise
