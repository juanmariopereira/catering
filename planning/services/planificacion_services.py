"""
Lógica de negocio para planificación de menús: listado, crear, editar, sustituciones, etiquetas, AJAX.
"""

from datetime import date, timedelta

from django.utils import timezone

from planning.models import (
    PlanificacionMenu,
    PlanificacionMenuReceta,
    PlanificacionClienteSustituta,
    PlanificacionClienteReceta,
)
from planning.utils import (
    clientes_no_gustan_por_receta,
    obtener_conflictos_menu_por_cliente_con_precarga,
    recetas_alternativas_para_momento_con_precarga,
    dieta_etiqueta_contrato,
    obtener_ingredientes_no_gustados_por_clientes,
    obtener_ingredientes_por_recetas,
)
from contracts.models import contratos_activos_en_fecha
from plans.models import Plan
from diets.models import TipoComida
from recipes.models import Receta, Ingrediente


def _parse_sort_planning(sort_param):
    result = []
    if not sort_param or not sort_param.strip():
        return result
    valid_cols = {'fecha', 'plan'}
    for part in sort_param.strip().split(','):
        part = part.strip()
        if ':' in part:
            col, dir_ = part.split(':', 1)
            col, dir_ = col.strip(), dir_.strip().lower()
            if col in valid_cols and dir_ in ('asc', 'desc'):
                result.append((col, dir_))
    return result


def _next_sort_planning(current_parsed, column):
    current_dir = next((d for c, d in current_parsed if c == column), None)
    if current_dir == 'desc':
        new_parsed = [(c, 'asc' if c == column else d) for c, d in current_parsed]
        return new_parsed, 'asc'
    if current_dir == 'asc':
        new_parsed = [(c, d) for c, d in current_parsed if c != column]
        return new_parsed, None
    new_parsed = current_parsed + [(column, 'desc')]
    return new_parsed, 'desc'


def _sort_to_string_planning(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


SORTABLE_COLUMNS_PLANNING = [('fecha', 'Fecha'), ('plan', 'Plan')]


def list_planificaciones_queryset(fecha_desde=None, fecha_hasta=None, plan_id=None, sort_param=None):
    qs = PlanificacionMenu.objects.all().select_related('plan')
    if fecha_desde:
        try:
            fd = date.fromisoformat(fecha_desde)
            qs = qs.filter(fecha__gte=fd)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = date.fromisoformat(fecha_hasta)
            qs = qs.filter(fecha__lte=fh)
        except ValueError:
            pass
    if plan_id:
        qs = qs.filter(plan_id=plan_id)
    sort_parsed = _parse_sort_planning(sort_param or '')
    if not sort_parsed:
        return qs.order_by('-fecha', 'plan__nombre')
    order_by_list = []
    for col, dir_ in sort_parsed:
        prefix = '' if dir_ == 'asc' else '-'
        if col == 'fecha':
            order_by_list.append(f'{prefix}fecha')
        elif col == 'plan':
            order_by_list.append(f'{prefix}plan__nombre')
    order_by_list.extend(['-fecha', 'plan__nombre'])
    return qs.order_by(*order_by_list)


def get_planificacion_list_context(get_params):
    get_copy = get_params.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    get_no_sort = get_params.copy()
    get_no_sort.pop('sort', None)
    get_no_sort.pop('page', None)
    sort_parsed = _parse_sort_planning(get_params.get('sort', ''))
    sort_headers = []
    for col_key, col_label in SORTABLE_COLUMNS_PLANNING:
        next_parsed, _ = _next_sort_planning(sort_parsed, col_key)
        next_sort = _sort_to_string_planning(next_parsed) if next_parsed else ''
        current_dir = next((d for c, d in sort_parsed if c == col_key), None)
        sort_headers.append({
            'sortable': True,
            'key': col_key,
            'label': col_label,
            'direction': current_dir,
            'next_sort': next_sort,
        })
    table_headers = [
        sort_headers[0],
        sort_headers[1],
        {'sortable': False, 'label': 'Acciones'},
    ]
    return {
        'planes': Plan.objects.filter(activo=True).order_by('nombre'),
        'query_string': get_copy.urlencode(),
        'query_base_no_sort': get_no_sort.urlencode(),
        'sort_headers': sort_headers,
        'table_headers': table_headers,
    }


def get_planificacion_existente_fecha_plan(fecha, plan_id):
    """Devuelve la planificación existente para (fecha, plan) o None."""
    try:
        f = date.fromisoformat(fecha) if isinstance(fecha, str) else fecha
    except (ValueError, TypeError):
        return None
    return PlanificacionMenu.objects.filter(fecha=f, plan_id=plan_id).first()


def get_planificacion_menu_create_initial(get_params):
    initial = {}
    fecha_param = get_params.get('fecha')
    if fecha_param:
        try:
            initial['fecha'] = date.fromisoformat(fecha_param)
        except ValueError:
            initial['fecha'] = timezone.now().date() + timedelta(days=1)
    else:
        initial['fecha'] = timezone.now().date() + timedelta(days=1)
    if get_params.get('plan'):
        initial['plan'] = get_params.get('plan')
    return initial


def get_planificacion_menu_create_context(fecha, plan_id):
    """Contexto para formulario de creación: planes y receta_counts para el formset."""
    receta_counts = clientes_no_gustan_por_receta(fecha, plan_id) if (fecha and plan_id) else {}
    return {
        'planes': Plan.objects.filter(activo=True).order_by('nombre'),
        'receta_counts': receta_counts,
    }


def get_recetas_por_tipo(tipo_comida_id):
    """Recetas activas para un tipo de comida (momentos_dia). Para AJAX."""
    try:
        tid = int(tipo_comida_id)
    except (ValueError, TypeError):
        return []
    return list(
        Receta.objects.filter(activa=True, momentos_dia__id=tid)
        .order_by('nombre')
        .values_list('id', 'nombre')
    )


def get_recetas_del_menu(planificacion_id, tipo_comida_id):
    """Recetas del menú de una planificación para un tipo de comida. Para AJAX."""
    try:
        pid = int(planificacion_id)
        tid = int(tipo_comida_id)
    except (ValueError, TypeError):
        return []
    menu = PlanificacionMenu.objects.filter(pk=pid).first()
    if not menu:
        return []
    return list(
        PlanificacionMenuReceta.objects.filter(
            planificacion_menu=menu,
            tipo_comida_id=tid,
        )
        .select_related('receta')
        .order_by('orden')
        .values_list('receta_id', 'receta__nombre')
    )


def get_etiqueta_dieta_data(planificacion_id, contrato_id):
    """
    Datos para etiqueta de dieta. Devuelve (data_dict, error_message).
    Si error_message no es None, el contrato no corresponde al plan o no hay datos.
    """
    from contracts.models import Contrato

    planificacion = PlanificacionMenu.objects.filter(pk=planificacion_id).select_related('plan').first()
    contrato = Contrato.objects.filter(pk=contrato_id).select_related('cliente', 'plan').first()
    if not planificacion or not contrato:
        return None, 'Planificación o contrato no encontrado.'
    if contrato.plan_id != planificacion.plan_id:
        return None, 'El contrato no corresponde al plan de esta planificación.'
    data = dieta_etiqueta_contrato(planificacion, contrato)
    if not data:
        return None, 'No hay datos de dieta para este cliente en esta fecha.'
    return data, None


def get_etiquetas_masivo_data(ids_param):
    """
    Lista de datos de etiquetas para impresión masiva.
    ids_param: "27/132,27/133" -> lista de dicts data para cada par válido.
    """
    from contracts.models import Contrato

    etiquetas = []
    for part in (ids_param or '').split(','):
        part = part.strip()
        if not part or '/' not in part:
            continue
        try:
            planificacion_id, contrato_id = part.split('/', 1)
            planificacion_id = int(planificacion_id.strip())
            contrato_id = int(contrato_id.strip())
        except (ValueError, TypeError):
            continue
        planificacion = PlanificacionMenu.objects.filter(pk=planificacion_id).select_related('plan').first()
        contrato = Contrato.objects.filter(pk=contrato_id).select_related('cliente', 'plan').first()
        if not planificacion or not contrato or contrato.plan_id != planificacion.plan_id:
            continue
        data = dieta_etiqueta_contrato(planificacion, contrato)
        if data:
            etiquetas.append(data)
    return etiquetas


def get_planificacion_menu_editar_context(planificacion_menu):
    """Contexto completo para edición de planificación menú (recetas, contratos, conflictos, excepciones)."""
    obj = planificacion_menu
    fecha = obj.fecha
    plan = obj.plan
    receta_counts = clientes_no_gustan_por_receta(fecha, plan) if (fecha and plan) else {}

    contratos = list(
        contratos_activos_en_fecha(fecha).filter(plan=plan).select_related('cliente')
    )
    contrato_ids = [c.id for c in contratos]
    cliente_ids = [c.cliente_id for c in contratos]

    sustituciones_actuales = {}
    for row in PlanificacionClienteSustituta.objects.filter(
        fecha=fecha, contrato_id__in=contrato_ids
    ).values_list('contrato_id', 'tipo_comida_id', 'receta_original_id', 'receta_sustituta_id'):
        sustituciones_actuales[(row[0], row[1], row[2])] = row[3]

    menu_recetas = list(
        PlanificacionMenuReceta.objects.filter(planificacion_menu=obj)
        .select_related('receta', 'tipo_comida')
        .prefetch_related('receta__tipos_receta')
        .order_by('tipo_comida__orden', 'orden')
    )
    receta_ids_menu = [mr.receta_id for mr in menu_recetas]

    recetas_todas = list(Receta.objects.filter(activa=True).order_by('nombre'))
    receta_ids_activas = [r.id for r in recetas_todas]

    ingredientes_no_gustados_por_cliente = obtener_ingredientes_no_gustados_por_clientes(cliente_ids)
    receta_ingredientes = obtener_ingredientes_por_recetas(receta_ids_menu)
    receta_ingredientes.update(obtener_ingredientes_por_recetas(receta_ids_activas))
    all_ing_ids = set()
    for ing_set in receta_ingredientes.values():
        all_ing_ids |= ing_set
    for ing_set in ingredientes_no_gustados_por_cliente.values():
        all_ing_ids |= ing_set
    ingredientes_por_id = Ingrediente.objects.in_bulk(all_ing_ids) if all_ing_ids else {}

    tipos_en_menu_ids = list({mr.tipo_comida_id for mr in menu_recetas})
    tipos_en_menu = list(
        TipoComida.objects.filter(id__in=tipos_en_menu_ids).order_by('orden', 'nombre')
    )

    recetas_por_tipo_comida = {}
    for tcid in tipos_en_menu_ids:
        recetas_por_tipo_comida[tcid] = list(
            Receta.objects.filter(activa=True, momentos_dia=tcid)
            .prefetch_related('tipos_receta')
            .order_by('nombre')
        )

    clientes_conflictos = []
    for c in contratos:
        ing_no_gusta = ingredientes_no_gustados_por_cliente.get(c.cliente_id, set())
        conflictos = obtener_conflictos_menu_por_cliente_con_precarga(
            menu_recetas, c, ing_no_gusta, receta_ingredientes, ingredientes_por_id
        )
        for cf in conflictos:
            tipo_receta_ids = [t.id for t in cf['receta'].tipos_receta.all()]
            cf['alternativas'] = recetas_alternativas_para_momento_con_precarga(
                cf['receta'].id,
                tipo_receta_ids if tipo_receta_ids else None,
                recetas_por_tipo_comida.get(cf['tipo_comida'].id, []),
                receta_ingredientes,
                ing_no_gusta,
            )
            ids_alt = {r.id for r in cf['alternativas']}
            cf['otras_recetas'] = [
                r for r in recetas_todas
                if r.id != cf['receta'].id and r.id not in ids_alt
            ]
            key = (c.id, cf['tipo_comida'].id, cf['receta'].id)
            cf['sustitucion_actual_id'] = sustituciones_actuales.get(key)
        clientes_conflictos.append({'contrato': c, 'conflictos': conflictos})

    lista_excepciones = list(
        PlanificacionClienteReceta.objects.filter(
            fecha=fecha, contrato_id__in=contrato_ids
        )
        .select_related('contrato__cliente', 'tipo_comida', 'receta', 'receta_original')
        .order_by('contrato__cliente__nombre', 'tipo_comida__orden', 'orden')
    )

    return {
        'contratos_fecha': contratos,
        'receta_counts': receta_counts,
        'tiene_momentos_en_menu': bool(tipos_en_menu),
        'clientes_conflictos': clientes_conflictos,
        'recetas_todas': recetas_todas,
        'show_dietas_personalizadas': True,
        'tipos_para_anadir': tipos_en_menu,
        'lista_excepciones': lista_excepciones,
        'contratos_para_anadir': [(c.id, c.cliente.nombre) for c in contratos],
    }


def guardar_sustituciones_from_post(planificacion_menu, post_data):
    """Guarda PlanificacionClienteSustituta desde POST (sustituir_contrato_X_tipo_Y_receta_Z)."""
    fecha = planificacion_menu.fecha
    for key in post_data:
        if not key.startswith('sustituir_contrato_'):
            continue
        parts = key.replace('sustituir_contrato_', '').split('_tipo_')
        if len(parts) != 2:
            continue
        try:
            contrato_id = int(parts[0])
        except ValueError:
            continue
        part2 = parts[1].split('_receta_')
        if len(part2) != 2:
            continue
        try:
            tipo_comida_id = int(part2[0])
            receta_original_id = int(part2[1])
        except ValueError:
            continue
        receta_sustituta_id = (post_data.get(key) or '').strip()
        if not receta_sustituta_id:
            PlanificacionClienteSustituta.objects.filter(
                fecha=fecha,
                contrato_id=contrato_id,
                tipo_comida_id=tipo_comida_id,
                receta_original_id=receta_original_id,
            ).delete()
            continue
        try:
            receta_sustituta_id = int(receta_sustituta_id)
        except (ValueError, TypeError):
            continue
        if receta_sustituta_id == receta_original_id:
            PlanificacionClienteSustituta.objects.filter(
                fecha=fecha,
                contrato_id=contrato_id,
                tipo_comida_id=tipo_comida_id,
                receta_original_id=receta_original_id,
            ).delete()
            continue
        PlanificacionClienteSustituta.objects.update_or_create(
            fecha=fecha,
            contrato_id=contrato_id,
            tipo_comida_id=tipo_comida_id,
            receta_original_id=receta_original_id,
            defaults={'receta_sustituta_id': receta_sustituta_id},
        )


def guardar_dietas_personalizadas_from_post(planificacion_menu, post_data):
    """Guarda excepciones de dieta: quitar (quitar_id) y añadir (nuevo_N_*)."""
    fecha = planificacion_menu.fecha
    quitar_ids = []
    for v in post_data.getlist('quitar_id'):
        try:
            quitar_ids.append(int(v))
        except (ValueError, TypeError):
            pass
    if quitar_ids:
        PlanificacionClienteReceta.objects.filter(pk__in=quitar_ids, fecha=fecha).delete()
    try:
        total = int(post_data.get('nuevo_excepciones_total', 1))
    except (ValueError, TypeError):
        total = 1
    for i in range(total):
        nuevo_contrato = (post_data.get('nuevo_%s_contrato' % i) or '').strip()
        nuevo_tipo = (post_data.get('nuevo_%s_tipo_comida' % i) or '').strip()
        nuevo_receta_original = (post_data.get('nuevo_%s_receta_original' % i) or '').strip()
        nuevo_receta = (post_data.get('nuevo_%s_receta' % i) or '').strip()
        if not nuevo_contrato or not nuevo_tipo or not nuevo_receta:
            continue
        try:
            contrato_id = int(nuevo_contrato)
            tipo_comida_id = int(nuevo_tipo)
            receta_id = int(nuevo_receta)
            receta_original_id = int(nuevo_receta_original) if nuevo_receta_original else None
        except (ValueError, TypeError):
            continue
        ultimo = PlanificacionClienteReceta.objects.filter(
            fecha=fecha, contrato_id=contrato_id, tipo_comida_id=tipo_comida_id
        ).order_by('-orden').values_list('orden', flat=True).first()
        orden = (ultimo or 0) + 1
        PlanificacionClienteReceta.objects.create(
            fecha=fecha,
            contrato_id=contrato_id,
            tipo_comida_id=tipo_comida_id,
            receta_original_id=receta_original_id,
            receta_id=receta_id,
            orden=orden,
        )


def actualizar_planificacion_menu(planificacion_menu, cleaned_data):
    """Actualiza fecha y plan de una planificación menú."""
    PlanificacionMenu.objects.filter(pk=planificacion_menu.pk).update(**cleaned_data)


def guardar_recetas_planificacion_menu(planificacion_menu, formset_cleaned_data):
    """
    Reemplaza las recetas del menú (PlanificacionMenuReceta) por la lista de formset_cleaned_data.
    Cada item: tipo_comida, receta, orden. Se ignoran los que tienen DELETE.
    """
    PlanificacionMenuReceta.objects.filter(planificacion_menu=planificacion_menu).delete()
    for row in formset_cleaned_data:
        if row.get('DELETE') or not row.get('receta'):
            continue
        PlanificacionMenuReceta.objects.create(
            planificacion_menu=planificacion_menu,
            tipo_comida=row['tipo_comida'],
            receta=row['receta'],
            orden=row.get('orden') or 0,
        )


def crear_planificacion_menu(form_cleaned_data):
    """Crea solo la PlanificacionMenu (sin recetas). Devuelve la instancia creada."""
    return PlanificacionMenu.objects.create(**form_cleaned_data)


def crear_planificacion_menu_con_recetas(form_cleaned_data, formset_cleaned_data):
    """
    Crea una PlanificacionMenu y sus PlanificacionMenuReceta.
    Devuelve la planificación creada.
    """
    planificacion = crear_planificacion_menu(form_cleaned_data)
    guardar_recetas_planificacion_menu(planificacion, formset_cleaned_data)
    return planificacion
