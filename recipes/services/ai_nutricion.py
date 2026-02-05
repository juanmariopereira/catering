"""
Servicio de información nutricional con IA.

- Estima info nutricional de ingredientes mediante OpenAI (por 100g).
- Calcula info nutricional de recetas a partir de ingredientes y cantidades.
"""
import json
import logging
import re
from decimal import Decimal
from typing import Any

from django.conf import settings

from base.ai_logging import extraer_usage, registrar_llamada_ia

logger = logging.getLogger(__name__)


def _buscar_ingrediente_en_catalogo(nombre_ai: str, nombre_to_id: dict[str, int]) -> int | None:
    """
    Busca el ID del ingrediente en el catálogo, tolerando variaciones como
    "Lechuga (kg)", "Lechuga 1", "Lechuga - kg", etc.
    """
    if not nombre_ai or not nombre_to_id:
        return None
    n = nombre_ai.strip().lower()
    if not n:
        return None
    # 1. Coincidencia exacta
    if n in nombre_to_id:
        return nombre_to_id[n]
    # 2. Quitar paréntesis: "Lechuga (kg)" -> "Lechuga"
    n_sin_parentesis = re.sub(r'\s*\([^)]*\)\s*', ' ', n).strip()
    if n_sin_parentesis and n_sin_parentesis in nombre_to_id:
        return nombre_to_id[n_sin_parentesis]
    # 3. Quitar guiones y unidades al final: "Lechuga - kg" -> "Lechuga"
    n_limpio = re.sub(r'\s*[-–]\s*(kg|gr|g|ml|l|un|ud)\s*$', '', n_sin_parentesis, flags=re.I).strip()
    if n_limpio and n_limpio in nombre_to_id:
        return nombre_to_id[n_limpio]
    # 4. Primera palabra/token antes de espacio+paréntesis: "Lechuga (kg)" -> "lechuga"
    primer_token = (re.split(r'[\s\(\)]', n)[0] or '').strip()
    if primer_token and primer_token in nombre_to_id:
        return nombre_to_id[primer_token]
    # 5. Nombre del catálogo al inicio del nombre de la IA (preferir coincidencias más largas)
    for cat_nombre in sorted(nombre_to_id.keys(), key=len, reverse=True):
        if n.startswith(cat_nombre) or n_sin_parentesis.startswith(cat_nombre):
            return nombre_to_id[cat_nombre]
    return None

# Unidades a gramos (para conversión a base común)
UNIDAD_A_GRAMOS = {
    'g': 1, 'gr': 1, 'gramo': 1, 'gramos': 1,
    'kg': 1000, 'kilogramo': 1000, 'kilogramos': 1000,
    'mg': 0.001, 'miligramo': 0.001, 'miligramos': 0.001,
    'ml': 1, 'mililitro': 1, 'mililitros': 1, 'cc': 1,  # densidad ~1 para líquidos
    'l': 1000, 'lt': 1000, 'litro': 1000, 'litros': 1000,
    'oz': 28.35, 'onza': 28.35, 'onzas': 28.35,
}


def _get_openai_client():
    """Obtiene el cliente de OpenAI."""
    from openai import OpenAI

    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise ValueError(
            'OPENAI_API_KEY no está configurada. '
            'Defínela en las variables de entorno para usar la estimación nutricional con IA.'
        )
    return OpenAI(api_key=api_key)


def estimar_info_nutricional_ingrediente(nombre_ingrediente: str, unidad_nombre: str, request=None) -> dict[str, Any]:
    """
    Estima la información nutricional de un ingrediente por 100g usando OpenAI.
    Para ingredientes por unidad (ej. huevo, manzana), incluye gramos_por_unidad estimado.

    Returns:
        Dict con estructura: {"por_100g": {...}, "gramos_por_unidad": N opcional}
    """
    client = _get_openai_client()

    system_prompt = """Eres un nutricionista experto. Estimas información nutricional de alimentos.
Responde ÚNICAMENTE con un JSON válido, sin texto adicional.
Formato: {"por_100g": {"calorias": N, "proteinas": N, "carbohidratos": N, "grasas": N, "fibra": N}, "alergenos": ["alergeno1", "alergeno2"]}
- Valores numéricos (por 100g de alimento).
- Si el ingrediente se vende por unidad (huevo, manzana, plátano), añade "gramos_por_unidad".
- "alergenos": lista de alérgenos que contiene (gluten, lactosa, frutos secos, mariscos, huevo, soja, apio, mostaza, sésamo, sulfitos, cacahuete, pescado). Lista vacía [] si no contiene ninguno.
Usa 0 cuando un nutriente sea insignificante."""

    user_prompt = f"""Ingrediente: {nombre_ingrediente}
Unidad de medida por defecto: {unidad_nombre}

Estima la información nutricional por 100g. Si es por unidad, incluye "gramos_por_unidad". Incluye "alergenos" con los alérgenos que puede contener.
Responde solo el JSON."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.2,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='estimar_nutricion_ingrediente',
            modelo='gpt-4o-mini',
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return {}

        data = json.loads(content)
        result = {}

        if 'por_100g' in data and isinstance(data['por_100g'], dict):
            por_100g = {k: float(v) if isinstance(v, (int, float)) else 0 for k, v in data['por_100g'].items()}
            result['por_100g'] = por_100g

        if 'gramos_por_unidad' in data:
            try:
                result['gramos_por_unidad'] = int(float(data['gramos_por_unidad']))
            except (TypeError, ValueError):
                pass

        if 'alergenos' in data and isinstance(data['alergenos'], list):
            result['alergenos'] = [str(a).strip() for a in data['alergenos'] if a]

        return result

    except json.JSONDecodeError as e:
        registrar_llamada_ia(
            accion='estimar_nutricion_ingrediente',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('OpenAI devolvió JSON inválido para ingrediente %s: %s', nombre_ingrediente, e)
        return {}
    except Exception as e:
        registrar_llamada_ia(
            accion='estimar_nutricion_ingrediente',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.exception('Error al estimar nutrición de %s: %s', nombre_ingrediente, e)
        raise


def _cantidad_a_gramos(cantidad: Decimal, unidad_simbolo: str, ingrediente) -> float:
    """
    Convierte cantidad + unidad a gramos.
    Para unidades como "unidad", usa gramos_por_unidad del ingrediente si existe.
    """
    u = (unidad_simbolo or '').strip().lower()
    if not u:
        u = (ingrediente.unidad_medida.simbolo or ingrediente.unidad_medida.nombre or '').lower()

    if u in UNIDAD_A_GRAMOS:
        return float(cantidad) * UNIDAD_A_GRAMOS[u]

    # Unidad, ud, etc. -> usar gramos_por_unidad del ingrediente
    if u in ('un', 'ud', 'unidad', 'unidades', 'u'):
        info = getattr(ingrediente, 'info_nutricional', None) or {}
        gramos = info.get('gramos_por_unidad')
        if gramos and gramos > 0:
            return float(cantidad) * gramos
        return 0  # sin conversión, no podemos calcular

    return 0


def calcular_info_nutricional_receta(receta) -> dict[str, float]:
    """
    Calcula la información nutricional total de una receta sumando los aportes
    de cada ingrediente según cantidad y su info nutricional por 100g.

    Returns:
        Dict: {"calorias": N, "proteinas": N, "carbohidratos": N, "grasas": N, "fibra": N}
        Solo incluye nutrientes presentes en los ingredientes.
    """
    from recipes.models import RecetaIngrediente

    totales: dict[str, float] = {}
    nutrientes_clave = ('calorias', 'proteinas', 'carbohidratos', 'grasas', 'fibra')

    for ri in RecetaIngrediente.objects.filter(receta=receta).select_related(
        'ingrediente', 'ingrediente__unidad_medida', 'unidad_medida'
    ):
        ingrediente = ri.ingrediente
        info = ingrediente.info_nutricional or {}
        por_100g = info.get('por_100g')
        if not por_100g or not isinstance(por_100g, dict):
            continue

        unidad_simbolo = (ri.unidad_medida.simbolo or ri.unidad_medida.nombre or '') if ri.unidad_medida else ''
        gramos = _cantidad_a_gramos(ri.cantidad, unidad_simbolo, ingrediente)
        if gramos <= 0:
            continue

        factor = gramos / 100.0
        for k in nutrientes_clave:
            if k in por_100g:
                try:
                    val = float(por_100g[k]) * factor
                except (TypeError, ValueError):
                    val = 0
                totales[k] = totales.get(k, 0) + val

    return {k: round(v, 1) for k, v in totales.items()}


def estimar_info_nutricional_receta_ia(receta, request=None) -> dict[str, Any]:
    """
    Estima la información nutricional de una receta usando IA cuando no puede
    calcularse desde los ingredientes (p. ej. ingredientes sin info_nutricional).

    Usa nombre, descripción y lista de ingredientes con cantidades para estimar.

    Returns:
        Dict: {"calorias": N, "proteinas": N, "carbohidratos": N, "grasas": N, "fibra": N}
    """
    from recipes.models import RecetaIngrediente

    client = _get_openai_client()

    # Construir descripción de ingredientes
    ingredientes_texto = []
    for ri in RecetaIngrediente.objects.filter(receta=receta).select_related(
        'ingrediente', 'unidad_medida'
    ):
        u = (ri.unidad_medida.simbolo or ri.unidad_medida.nombre or '') if ri.unidad_medida else ''
        ingredientes_texto.append(f"- {ri.ingrediente.nombre}: {ri.cantidad} {u}")
    ingredientes_str = "\n".join(ingredientes_texto) if ingredientes_texto else "Sin ingredientes especificados"

    descripcion = (receta.descripcion or "")[:300]

    system_prompt = """Eres un nutricionista. Estimas la información nutricional total de una receta
(porción completa/ración típica) a partir de su nombre, descripción e ingredientes.
Responde ÚNICAMENTE con un JSON válido: {"calorias": N, "proteinas": N, "carbohidratos": N, "grasas": N, "fibra": N}
Valores numéricos para la receta completa (una ración típica). Usa 0 cuando un nutriente sea insignificante."""

    user_prompt = f"""Receta: {receta.nombre}
Descripción: {descripcion}
Ingredientes:
{ingredientes_str}

Estima calorías y macronutrientes para una ración típica de esta receta. Responde solo el JSON."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.2,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='estimar_nutricion_receta',
            modelo='gpt-4o-mini',
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return {}

        data = json.loads(content)
        nutrientes = ('calorias', 'proteinas', 'carbohidratos', 'grasas', 'fibra')
        result = {}
        for k in nutrientes:
            if k in data:
                try:
                    result[k] = round(float(data[k]), 1)
                except (TypeError, ValueError):
                    result[k] = 0
        return result

    except (json.JSONDecodeError, Exception) as e:
        registrar_llamada_ia(
            accion='estimar_nutricion_receta',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('Error al estimar nutrición receta %s: %s', receta.nombre, e)
        return {}


def sugerir_descripcion_receta_ia(receta, request=None) -> str:
    """
    Sugiere una descripción para una receta usando IA, basada en nombre,
    tipos, momentos e ingredientes.
    """
    from recipes.models import RecetaIngrediente

    client = _get_openai_client()

    ingredientes_texto = []
    for ri in RecetaIngrediente.objects.filter(receta=receta).select_related(
        'ingrediente', 'unidad_medida'
    ):
        u = (ri.unidad_medida.simbolo or ri.unidad_medida.nombre or '') if ri.unidad_medida else ''
        ingredientes_texto.append(f"- {ri.ingrediente.nombre}: {ri.cantidad} {u}")
    ingredientes_str = "\n".join(ingredientes_texto) if ingredientes_texto else "Sin ingredientes"

    tipos = [t.nombre for t in receta.tipos_receta.all()]
    momentos = [m.nombre for m in receta.momentos_dia.all()]

    system_prompt = """Eres un chef y redactor de recetas. Escribes descripciones breves y atractivas
para recetas de catering/comida saludable. La descripción debe ser 2-4 oraciones, en español,
destacando el plato, sus ingredientes principales y para qué momento es adecuado."""

    user_prompt = f"""Receta: {receta.nombre}
Tipo(s): {', '.join(tipos) if tipos else '—'}
Momento(s) del día: {', '.join(momentos) if momentos else '—'}
Ingredientes:
{ingredientes_str}

Escribe una descripción breve y atractiva para esta receta. Solo el texto, sin título ni formato especial."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.6,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='sugerir_descripcion_receta',
            modelo='gpt-4o-mini',
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = (response.choices[0].message.content or '').strip()
        return content
    except Exception as e:
        registrar_llamada_ia(
            accion='sugerir_descripcion_receta',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('Error al sugerir descripción para %s: %s', receta.nombre, e)
        return ''


def sugerir_ingredientes_receta_ia(receta, request=None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """
    Sugiere ingredientes y cantidades para una receta usando IA.
    Puede sugerir cualquier ingrediente por nombre; los que no existan en catálogo
    se devuelven en no_encontrados para añadirlos a la descripción.

    Returns:
        (ingredientes, no_encontrados, catalogo_vacio)
        - ingredientes: [{"ingrediente_id": int, "cantidad": float, "unidad_medida_id": int}]
        - no_encontrados: [{"nombre": str, "cantidad": float, "unidad": str}] para añadir a descripción
        - catalogo_vacio: True si no hay ingredientes en el catálogo
    """
    from recipes.models import Ingrediente, UnidadMedida

    client = _get_openai_client()

    ingredientes_cat = list(
        Ingrediente.objects.filter(activo=True).values('id', 'nombre')
    )
    unidades_cat = list(
        UnidadMedida.objects.filter(activo=True).values('id', 'nombre', 'simbolo')
    )

    tipos = [t.nombre for t in receta.tipos_receta.all()]
    momentos = [m.nombre for m in receta.momentos_dia.all()]

    catalogo_vacio = not ingredientes_cat

    system_prompt = """Eres un chef experto. Sugieres ingredientes para una receta de catering/comida saludable.
Responde ÚNICAMENTE con un JSON: {"ingredientes": [{"nombre_ingrediente": "texto", "cantidad": N, "unidad": "gr" o "kg" o "ml" o "un" etc.}, ...]}
Usa nombres de ingredientes (en español). Cantidades numéricas razonables. Unidades: gr, kg, ml, l, un, etc."""

    if catalogo_vacio:
        cat_bloque = """NO hay ingredientes en el catálogo actualmente. Sugiere los ingredientes típicos para esta receta con cantidades razonables.
El usuario los añadirá manualmente al catálogo y a la receta."""
    else:
        cat_bloque = f"""Ingredientes disponibles en el catálogo (prioriza estos si aplican):
{json.dumps([i['nombre'] for i in ingredientes_cat], ensure_ascii=False)}

Sugiere ingredientes con cantidades. Prioriza los del catálogo cuando encajen."""

    user_prompt = f"""Receta: {receta.nombre}
Descripción: {receta.descripcion or '—'}
Tipo(s): {', '.join(tipos) if tipos else '—'}
Momento(s): {', '.join(momentos) if momentos else '—'}

{cat_bloque}
Responde solo el JSON con clave "ingredientes"."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.5,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='sugerir_ingredientes_receta',
            modelo='gpt-4o-mini',
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return [], [], catalogo_vacio

        data = json.loads(content)
        items = data.get('ingredientes', data.get('items', []))
        if not isinstance(items, list):
            return [], [], catalogo_vacio

        nombre_to_id = {i['nombre'].strip().lower(): i['id'] for i in ingredientes_cat}
        unidad_map = {}
        for u in unidades_cat:
            for key in [u['nombre'], u.get('simbolo')]:
                if key:
                    unidad_map[str(key).strip().lower()] = u['id']

        ingredientes = []
        no_encontrados = []

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                nombre = str(item.get('nombre_ingrediente', '')).strip()
                cant = float(item.get('cantidad', 1))
                unidad_str = str(item.get('unidad', '')).strip().lower()
            except (TypeError, ValueError):
                continue
            if not nombre or cant <= 0:
                continue

            ing_id = _buscar_ingrediente_en_catalogo(nombre, nombre_to_id)
            uni_id = unidad_map.get(unidad_str) if unidad_str else None
            if not uni_id and unidades_cat:
                uni_id = unidades_cat[0]['id']

            if ing_id and uni_id:
                ingredientes.append({
                    'ingrediente_id': ing_id,
                    'cantidad': round(cant, 2),
                    'unidad_medida_id': uni_id,
                })
            else:
                no_encontrados.append({
                    'nombre': nombre,
                    'cantidad': round(cant, 2),
                    'unidad': unidad_str or '—',
                })

        return ingredientes, no_encontrados, catalogo_vacio

    except Exception as e:
        registrar_llamada_ia(
            accion='sugerir_ingredientes_receta',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='receta',
            objeto_id=receta.pk if receta else None,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('Error al sugerir ingredientes para %s: %s', receta.nombre, e)
        return [], [], False


def importar_receta_desde_texto_ia(texto: str, request=None) -> dict[str, Any]:
    """
    Importa una receta desde texto pegado (de web, libro, etc.) usando IA.
    Extrae nombre, descripción, tipo(s), momento(s) e ingredientes con cantidades.
    Los ingredientes se intentan mapear al catálogo; los no encontrados se devuelven aparte.

    Returns:
        Dict con: nombre, descripcion, tipos_receta_ids, momentos_dia_ids,
        ingredientes: [{ingrediente_id, cantidad, unidad_medida_id}],
        no_encontrados: [{nombre, cantidad, unidad}],
        nota_descripcion: texto para añadir a descripcion si hay no_encontrados
    """
    from recipes.models import Ingrediente, UnidadMedida, TipoReceta
    from diets.models import TipoComida

    client = _get_openai_client()

    ingredientes_cat = list(Ingrediente.objects.filter(activo=True).values('id', 'nombre'))
    unidades_cat = list(UnidadMedida.objects.filter(activo=True).values('id', 'nombre', 'simbolo'))
    tipos_receta = list(TipoReceta.objects.filter(activo=True).order_by('orden', 'nombre').values('id', 'nombre'))
    momentos_dia = list(TipoComida.objects.order_by('orden', 'nombre').values('id', 'nombre'))

    system_prompt = """Eres un asistente experto en extraer información estructurada de recetas de cocina.
Analizas el texto pegado (que puede venir de webs, blogs, libros) y extraes:
- nombre: nombre de la receta
- descripcion: descripción breve (2-4 oraciones) del plato
- tipos_receta: lista de nombres que encajen (Comida, Postre, Bebida, Complemento, Masa, Fruta, etc.)
- momentos_dia: lista de momentos (Desayuno, Media mañana, Comida, Merienda, Cena)
- ingredientes: lista de {nombre_ingrediente, cantidad, unidad} - cantidad numérica, unidad en gr/kg/ml/l/un

Responde ÚNICAMENTE con un JSON válido:
{"nombre": "...", "descripcion": "...", "tipos_receta": ["tipo1"], "momentos_dia": ["momento1"], "ingredientes": [{"nombre_ingrediente": "...", "cantidad": N, "unidad": "gr"|"kg"|"ml"|"un"|...}]}

Usa los nombres EXACTOS de tipos y momentos de las listas proporcionadas cuando encajen. Para ingredientes usa español.
Unidades típicas: gr, kg, ml, l, un, ud, taza, cucharada."""

    cat_tipos = json.dumps([t['nombre'] for t in tipos_receta], ensure_ascii=False)
    cat_momentos = json.dumps([m['nombre'] for m in momentos_dia], ensure_ascii=False)
    cat_ing = json.dumps([i['nombre'] for i in ingredientes_cat], ensure_ascii=False)

    user_prompt = f"""Texto de la receta a importar:

---
{texto[:4000]}
---

Tipos de receta disponibles (usa exactos si encajan): {cat_tipos}
Momentos del día disponibles (usa exactos si encajan): {cat_momentos}
Ingredientes del catálogo (prioriza estos nombres): {cat_ing}

Extrae la receta en JSON. Para ingredientes, si el nombre coincide con el catálogo úsalo; si no, sugiere el más cercano en español."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.3,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='importar_receta',
            modelo='gpt-4o-mini',
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = response.choices[0].message.content
        if not content:
            return {}

        data = json.loads(content)
        nombre = (data.get('nombre') or '').strip() or 'Receta importada'
        descripcion = (data.get('descripcion') or '').strip()
        tipos_nombres = data.get('tipos_receta', data.get('tipos', []))
        momentos_nombres = data.get('momentos_dia', data.get('momentos', []))
        items = data.get('ingredientes', data.get('items', []))

        if not isinstance(tipos_nombres, list):
            tipos_nombres = []
        if not isinstance(momentos_nombres, list):
            momentos_nombres = []
        if not isinstance(items, list):
            items = []

        nombre_to_tipo_id = {str(t['nombre']).strip().lower(): t['id'] for t in tipos_receta}
        nombre_to_momento_id = {str(m['nombre']).strip().lower(): m['id'] for m in momentos_dia}
        nombre_to_ing_id = {str(i['nombre']).strip().lower(): i['id'] for i in ingredientes_cat}
        unidad_map = {}
        for u in unidades_cat:
            for key in [u['nombre'], u.get('simbolo')]:
                if key:
                    unidad_map[str(key).strip().lower()] = u['id']
        if unidades_cat and not unidad_map:
            unidad_map['un'] = unidades_cat[0]['id']

        tipos_ids = []
        for t in tipos_nombres:
            tid = nombre_to_tipo_id.get(str(t).strip().lower())
            if tid and tid not in tipos_ids:
                tipos_ids.append(tid)

        momentos_ids = []
        for m in momentos_nombres:
            mid = nombre_to_momento_id.get(str(m).strip().lower())
            if mid and mid not in momentos_ids:
                momentos_ids.append(mid)

        ingredientes = []
        no_encontrados = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                nom = str(item.get('nombre_ingrediente', item.get('nombre', ''))).strip()
                cant = float(item.get('cantidad', 1))
                uni_str = str(item.get('unidad', '')).strip().lower()
            except (TypeError, ValueError):
                continue
            if not nom or cant <= 0:
                continue

            ing_id = _buscar_ingrediente_en_catalogo(nom, nombre_to_ing_id)
            uni_id = unidad_map.get(uni_str) if uni_str else (unidades_cat[0]['id'] if unidades_cat else None)
            if ing_id and uni_id:
                ingredientes.append({
                    'ingrediente_id': ing_id,
                    'cantidad': round(cant, 2),
                    'unidad_medida_id': uni_id,
                })
            else:
                no_encontrados.append({
                    'nombre': nom,
                    'cantidad': round(cant, 2),
                    'unidad': uni_str or '—',
                })

        nota = ''
        if no_encontrados:
            lista = ', '.join(f"{x['nombre']} ({x['cantidad']} {x['unidad']})" for x in no_encontrados)
            catalogo_vacio = not ingredientes_cat
            nota = f"No hay ingredientes en el catálogo. " if catalogo_vacio else ""
            nota += f"Ingredientes no encontrados (añadir al catálogo): {lista}"

        return {
            'nombre': nombre,
            'descripcion': descripcion,
            'tipos_receta_ids': tipos_ids,
            'momentos_dia_ids': momentos_ids,
            'ingredientes': ingredientes,
            'no_encontrados': no_encontrados,
            'nota_descripcion': nota,
        }

    except Exception as e:
        registrar_llamada_ia(
            accion='importar_receta',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('Error al importar receta desde texto: %s', e)
        raise


def obtener_alergenos_receta(receta) -> list[str]:
    """
    Devuelve la lista de alérgenos presentes en una receta, según los ingredientes.
    """
    from recipes.models import RecetaIngrediente

    alergenos = set()
    for ri in RecetaIngrediente.objects.filter(receta=receta).select_related('ingrediente'):
        ing_alerg = getattr(ri.ingrediente, 'alergenos', None) or []
        if isinstance(ing_alerg, list):
            for a in ing_alerg:
                if a:
                    alergenos.add(str(a).strip())
    return sorted(alergenos)
