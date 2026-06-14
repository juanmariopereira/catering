"""
Servicio de generación de menús con OpenAI.

Genera sugerencias de menú (recetas por momento del día) considerando:
- Recetas disponibles y sus momentos apropiados
- Menús recientes para evitar repeticiones
- Dietas asociadas al plan
- Variedad y equilibrio
"""
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings

from base.ai_logging import extraer_usage, registrar_llamada_ia

logger = logging.getLogger(__name__)


def _get_openai_client():
    """Obtiene el cliente de OpenAI (lazy para evitar import al arrancar)."""
    from openai import OpenAI

    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise ValueError(
            'OPENAI_API_KEY no está configurada. '
            'Defínela en las variables de entorno para usar la sugerencia de menús con IA.'
        )
    return OpenAI(api_key=api_key)


def _normalize_info_nutricional(info: Optional[Dict]) -> Optional[Dict]:
    """
    Normaliza info nutricional a un dict plano con calorias, proteinas, carbohidratos, grasas, fibra.
    Acepta formato plano o anidado (por_100g). Devuelve None si no hay datos útiles.
    """
    if not info or not isinstance(info, dict):
        return None
    flat = {}
    if 'por_100g' in info and isinstance(info['por_100g'], dict):
        flat = {k: v for k, v in info['por_100g'].items() if k in ('calorias', 'proteinas', 'carbohidratos', 'grasas', 'fibra')}
    for k in ('calorias', 'proteinas', 'carbohidratos', 'grasas', 'fibra'):
        if k in info and info[k] is not None:
            try:
                flat[k] = float(info[k])
            except (TypeError, ValueError):
                pass
    return flat if flat else None


def _build_context(fecha, plan):
    """
    Construye el contexto para el prompt: tipos de comida, recetas (con info nutricional), menús recientes, dietas.
    """
    from diets.models import DietaReceta, TipoComida
    from planning.models import PlanificacionMenu, PlanificacionMenuReceta
    from recipes.models import Receta
    from recipes.services.ai_nutricion import calcular_info_nutricional_receta

    # Tipos de comida (momentos del día)
    tipos_comida = list(
        TipoComida.objects.order_by('orden', 'nombre').values('id', 'nombre', 'orden')
    )

    # Recetas activas con sus tipos, momentos e información nutricional
    recetas = []
    for r in Receta.objects.filter(activa=True).prefetch_related(
        'tipos_receta', 'momentos_dia'
    ).order_by('nombre'):
        tipos = [t.nombre for t in r.tipos_receta.all()]
        momentos = [m.nombre for m in r.momentos_dia.all()]
        info_nutri = _normalize_info_nutricional(r.info_nutricional)
        if not info_nutri:
            try:
                info_nutri = calcular_info_nutricional_receta(r)
            except Exception:
                info_nutri = None
        item = {
            'id': r.id,
            'nombre': r.nombre,
            'tipos': tipos,
            'momentos_aptos': momentos,
        }
        if info_nutri:
            item['info_nutricional'] = info_nutri
        recetas.append(item)

    # Menús recientes del mismo plan (últimos 14 días) para evitar repetición
    fecha_desde = fecha - timedelta(days=14)
    menus_recientes = []
    for pm in PlanificacionMenu.objects.filter(
        plan=plan,
        fecha__gte=fecha_desde,
        fecha__lt=fecha,
    ).prefetch_related('recetas__receta', 'recetas__tipo_comida').order_by('-fecha')[:7]:
        items = []
        for mr in pm.recetas.all().order_by('tipo_comida__orden', 'orden'):
            items.append({
                'momento': mr.tipo_comida.nombre,
                'receta': mr.receta.nombre,
            })
        if items:
            menus_recientes.append({'fecha': str(pm.fecha), 'items': items})

    # Dietas asociadas al plan (patrón típico de recetas por momento)
    dietas_del_plan = []
    for dr in DietaReceta.objects.filter(
        dieta__planes=plan,
        dieta__activa=True,
    ).select_related('dieta', 'tipo_comida', 'receta').order_by('dieta__nombre', 'tipo_comida__orden', 'orden')[:50]:
        dietas_del_plan.append({
            'dieta': dr.dieta.nombre,
            'momento': dr.tipo_comida.nombre,
            'receta': dr.receta.nombre,
        })

    return {
        'tipos_comida': tipos_comida,
        'recetas': recetas,
        'menus_recientes': menus_recientes,
        'dietas_del_plan': dietas_del_plan,
        'plan_nombre': plan.nombre,
        'fecha': str(fecha),
        'dia_semana': fecha.strftime('%A'),
    }


def sugerir_menu_ia(fecha, plan, request=None, idea_menu: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Sugiere un menú usando OpenAI.

    Args:
        fecha: fecha del menú
        plan: instancia de Plan
        idea_menu: opcional; idea o preferencia del usuario para el menú (ej: "menú ligero", "más verduras")

    Returns:
        Lista de dicts: [{"tipo_comida_id": int, "receta_id": int, "orden": int}, ...]
        Vacía si hay error o no hay API key.

    Raises:
        ValueError: si OPENAI_API_KEY no está configurada
    """
    client = _get_openai_client()
    ctx = _build_context(fecha, plan)

    tipos_json = json.dumps(ctx['tipos_comida'], ensure_ascii=False)
    recetas_json = json.dumps(ctx['recetas'], ensure_ascii=False)
    menus_json = json.dumps(ctx['menus_recientes'], ensure_ascii=False)
    dietas_json = json.dumps(ctx['dietas_del_plan'], ensure_ascii=False)

    system_prompt = """Eres un asistente experto en planificación de menús para un servicio de catering.
Tu tarea es proponer un menú diario variado y equilibrado, asignando recetas a cada momento del día (Desayuno, Media mañana, Comida, Merienda, Cena).

Reglas:
1. Solo puedes usar recetas de la lista proporcionada (id y nombre). No inventes recetas.
2. Asigna recetas que sean apropiadas para cada momento (usa "momentos_aptos" cuando exista).
3. Evita repetir recetas que ya se usaron en menús recientes del mismo plan.
4. Ten en cuenta las dietas típicas del plan para mantener coherencia.
5. Incluye variedad: distintos tipos (comida, postre, bebida, fruta, etc.) según el momento.
6. Cada momento puede tener varias recetas (ej. media mañana: té + galleta + fruta). Ordena con "orden" 1, 2, 3...
7. Si el usuario indica una idea o preferencia para el menú, tenla en cuenta al elegir recetas (ej: "menú ligero", "más verduras", "sin fritos").
8. Las recetas pueden incluir "info_nutricional" (calorías, proteínas, carbohidratos, grasas, fibra por receta). Cuando el usuario pida criterios nutricionales (ej: menú hipercalórico, bajo en calorías, alto en proteínas, light, bajo en grasas), usa estos datos para elegir recetas que cumplan esa idea. Prioriza recetas con info_nutricional cuando el criterio sea nutricional.
9. Responde ÚNICAMENTE con un JSON válido: un objeto con clave "recetas" que sea un array de objetos.
   Cada objeto del array debe tener: tipo_comida_id, receta_id, orden.
   Ejemplo: {"recetas": [{"tipo_comida_id": 1, "receta_id": 5, "orden": 1}, {"tipo_comida_id": 1, "receta_id": 12, "orden": 2}]}"""

    idea_line = ""
    if idea_menu:
        idea_line = f"\nIdea o preferencia del usuario para este menú: {idea_menu}\n"

    user_prompt = f"""Plan: {ctx['plan_nombre']}
Fecha: {ctx['fecha']} ({ctx['dia_semana']})
{idea_line}
Tipos de comida (momentos del día):
{tipos_json}

Recetas disponibles (id, nombre, tipos, momentos_aptos, info_nutricional cuando exista: calorías, proteínas, carbohidratos, grasas, fibra por receta):
{recetas_json}

Menús recientes de este plan (evitar repetir las mismas recetas):
{menus_json}

Dietas típicas del plan (referencia de recetas por momento):
{dietas_json}

Genera un menú variado para esta fecha.{" Ten en cuenta la idea del usuario indicada arriba." if idea_menu else ""} Responde solo con el JSON (objeto con clave "recetas"), sin texto adicional."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.7,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='sugerir_menu',
            modelo='gpt-4o-mini',
            objeto_tipo='plan',
            objeto_id=plan.pk if plan else None,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return []

        data = json.loads(content)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('recetas', data.get('menu', data.get('items', [])))
        else:
            return []

        if not isinstance(items, list):
            return []

        # Validar y filtrar: solo IDs válidos
        tipo_ids = {t['id'] for t in ctx['tipos_comida']}
        receta_ids = {r['id'] for r in ctx['recetas']}
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tc_id = item.get('tipo_comida_id')
            rec_id = item.get('receta_id')
            orden = item.get('orden', 1)
            if tc_id is None or rec_id is None:
                continue
            try:
                tc_id = int(tc_id)
                rec_id = int(rec_id)
                orden = max(1, int(orden))
            except (TypeError, ValueError):
                continue
            if tc_id in tipo_ids and rec_id in receta_ids:
                result.append({
                    'tipo_comida_id': tc_id,
                    'receta_id': rec_id,
                    'orden': orden,
                })

        return result

    except json.JSONDecodeError as e:
        registrar_llamada_ia(
            accion='sugerir_menu',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='plan',
            objeto_id=plan.pk if plan else None,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('OpenAI devolvió JSON inválido: %s', e)
        return []
    except Exception as e:
        registrar_llamada_ia(
            accion='sugerir_menu',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='plan',
            objeto_id=plan.pk if plan else None,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.exception('Error al llamar a OpenAI para sugerir menú: %s', e)
        raise
