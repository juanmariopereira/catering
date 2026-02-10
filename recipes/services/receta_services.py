"""
Lógica de negocio para recetas: listado, contextos, planificaciones, duplicar, importar.
"""

from collections import defaultdict

from django.db.models import Q, Min, Value
from django.db.models.functions import Coalesce

from planning.models import PlanificacionMenuReceta
from recipes.models import Receta, RecetaIngrediente, TipoReceta, UnidadMedida, Ingrediente
from diets.models import TipoComida


def parse_sort_receta(sort_param):
    """'nombre:desc,tipo:asc' -> [('nombre', 'desc'), ('tipo', 'asc')]"""
    result = []
    if not sort_param or not sort_param.strip():
        return result
    valid_cols = {'nombre', 'tipo', 'momento', 'cocina'}
    for part in sort_param.strip().split(','):
        part = part.strip()
        if ':' in part:
            col, dir_ = part.split(':', 1)
            col, dir_ = col.strip(), dir_.strip().lower()
            if col in valid_cols and dir_ in ('asc', 'desc'):
                result.append((col, dir_))
    return result


def next_sort_receta(current_parsed, column):
    """Ciclo: (ninguno) -> desc -> asc -> (ninguno)."""
    current_dir = next((d for c, d in current_parsed if c == column), None)
    if current_dir == 'desc':
        new_parsed = [(c, 'asc' if c == column else d) for c, d in current_parsed]
        return new_parsed, 'asc'
    if current_dir == 'asc':
        new_parsed = [(c, d) for c, d in current_parsed if c != column]
        return new_parsed, None
    new_parsed = current_parsed + [(column, 'desc')]
    return new_parsed, 'desc'


def sort_to_string_receta(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


SORTABLE_COLUMNS_RECETA = [
    ('nombre', 'Nombre'),
    ('tipo', 'Tipo de receta'),
    ('momento', 'Momentos día'),
    ('cocina', 'Cocina'),
]


def list_recetas_queryset(
    *,
    busqueda=None,
    tipo_receta_id=None,
    momento_id=None,
    activa=None,
    sort_param=None,
):
    """Queryset de recetas filtrado y ordenado."""
    qs = Receta.objects.all()
    if busqueda:
        qs = qs.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
    if tipo_receta_id:
        qs = qs.filter(tipos_receta=tipo_receta_id)
    if momento_id:
        qs = qs.filter(momentos_dia_id=momento_id)
    if activa is not None and activa != '':
        qs = qs.filter(activa=activa == '1')
    qs = qs.annotate(
        orden_tipo=Coalesce(Min('tipos_receta__nombre'), Value('')),
        orden_momento=Coalesce(Min('momentos_dia__nombre'), Value('')),
    )
    sort_parsed = parse_sort_receta(sort_param or '')
    if not sort_parsed:
        return qs.order_by('nombre', 'orden_tipo', 'orden_momento', 'producido_en_cocina')
    order_by_list = []
    for col, dir_ in sort_parsed:
        prefix = '' if dir_ == 'asc' else '-'
        if col == 'nombre':
            order_by_list.append(f'{prefix}nombre')
        elif col == 'tipo':
            order_by_list.append(f'{prefix}orden_tipo')
        elif col == 'momento':
            order_by_list.append(f'{prefix}orden_momento')
        elif col == 'cocina':
            order_by_list.append(f'{prefix}producido_en_cocina')
    order_by_list.append('nombre')
    return qs.order_by(*order_by_list)


def get_receta_list_context(get_params):
    """Contexto para lista de recetas: tipos, momentos, query_string, sort_headers, table_headers."""
    get_copy = get_params.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    get_no_sort = get_params.copy()
    get_no_sort.pop('sort', None)
    get_no_sort.pop('page', None)
    sort_parsed = parse_sort_receta(get_params.get('sort', ''))
    sort_headers = []
    for col_key, col_label in SORTABLE_COLUMNS_RECETA:
        next_parsed, _ = next_sort_receta(sort_parsed, col_key)
        next_sort_str = sort_to_string_receta(next_parsed) if next_parsed else ''
        current_dir = next((d for c, d in sort_parsed if c == col_key), None)
        sort_headers.append({
            'sortable': True,
            'key': col_key,
            'label': col_label,
            'direction': current_dir,
            'next_sort': next_sort_str,
        })
    table_headers = [
        sort_headers[0], sort_headers[1], sort_headers[2],
        {'sortable': False, 'label': 'Ingredientes'},
        {'sortable': False, 'label': 'Estado'},
        sort_headers[3],
        {'sortable': False, 'label': 'Acciones'},
    ]
    return {
        'tipos_receta': TipoReceta.objects.filter(activo=True).order_by('orden', 'nombre'),
        'momentos_dia': TipoComida.objects.all().order_by('orden', 'nombre'),
        'query_string': get_copy.urlencode(),
        'query_base_no_sort': get_no_sort.urlencode(),
        'sort_headers': sort_headers,
        'table_headers': table_headers,
    }


def get_receta_update_context(receta):
    """Contexto para formulario de edición de receta: unidades, ingredientes, planificaciones."""
    from .ingrediente_services import get_unidad_medida_unidad_ids

    unidades = UnidadMedida.objects.filter(activo=True).order_by('orden', 'nombre')
    unidad_gramo = unidades.filter(
        Q(nombre__iexact='Gramo') | Q(simbolo__iexact='gr')
    ).first()
    ingredientes_con_unidad = Ingrediente.objects.select_related('unidad_medida').only(
        'pk', 'unidad_medida_id', 'nombre'
    )
    ingredientes_lista = list(
        Ingrediente.objects.order_by('nombre').only('pk', 'nombre')
    )
    return {
        'planificaciones_con_receta': planificaciones_que_incluyen_receta(receta),
        'unidades_medida': unidades,
        'unidad_medida_por_defecto_id': unidad_gramo.pk if unidad_gramo else None,
        'ingrediente_unidad_defecto': {
            str(ing.pk): ing.unidad_medida_id for ing in ingredientes_con_unidad
        },
        'ingrediente_tipo_unidad': {
            str(ing.pk): (ing.unidad_medida.tipo if ing.unidad_medida_id else 'peso')
            for ing in ingredientes_con_unidad
        },
        'ingredientes_lista': [{'id': ing.pk, 'nombre': ing.nombre} for ing in ingredientes_lista],
        'unidad_medida_unidad_ids': get_unidad_medida_unidad_ids(),
        'unidad_tipo_by_id': {
            str(u.pk): (u.tipo or 'peso')
            for u in UnidadMedida.objects.filter(activo=True)
        },
    }


def crear_receta_desde_importacion(data):
    """
    Crea una Receta a partir del dict devuelto por importar_receta_desde_texto_ia.
    data: nombre, descripcion?, nota_descripcion?, tipos_receta_ids?, momentos_dia_ids?, ingredientes?
    Devuelve la receta creada.
    """
    descripcion = data.get('descripcion', '')
    if data.get('nota_descripcion'):
        descripcion = (descripcion + '\n\n' + data['nota_descripcion']).strip()
    receta = Receta.objects.create(
        nombre=data['nombre'],
        descripcion=descripcion or None,
        info_nutricional={},
        activa=True,
    )
    receta.tipos_receta.set(data.get('tipos_receta_ids', []))
    receta.momentos_dia.set(data.get('momentos_dia_ids', []))
    for ing in data.get('ingredientes', []):
        RecetaIngrediente.objects.create(
            receta=receta,
            ingrediente_id=ing['ingrediente_id'],
            cantidad=ing['cantidad'],
            unidad_medida_id=ing['unidad_medida_id'],
        )
    return receta


def list_tipos_receta_queryset():
    """Queryset de tipos de receta ordenados."""
    return TipoReceta.objects.all().order_by('orden', 'nombre')


def list_unidades_medida_queryset():
    """Queryset de unidades de medida ordenadas."""
    return UnidadMedida.objects.all().order_by('orden', 'nombre')


def get_ingrediente_form_context():
    """Contexto común para formularios de ingrediente (create/update): unidad_medida_unidad_ids."""
    from .ingrediente_services import get_unidad_medida_unidad_ids
    return {'unidad_medida_unidad_ids': get_unidad_medida_unidad_ids()}


def get_ingrediente_list_context(get_params):
    """Contexto para lista de ingredientes: query_string."""
    get_copy = get_params.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    return {'query_string': get_copy.urlencode()}


def get_receta_detalle_context(receta):
    """Contexto para vista de detalle de receta: alergenos y planificaciones."""
    from .ai_nutricion import obtener_alergenos_receta
    return {
        'alergenos': obtener_alergenos_receta(receta),
        'planificaciones_con_receta': planificaciones_que_incluyen_receta(receta),
    }


def actualizar_receta(receta, form_cleaned_data, formset_cleaned_data):
    """
    Actualiza una receta y sus ingredientes a partir de form.cleaned_data y formset.cleaned_data.
    formset_cleaned_data: lista de dicts con ingrediente, cantidad, unidad_medida (se ignoran los que tienen DELETE).
    """
    data = dict(form_cleaned_data)
    tipos = data.pop('tipos_receta', None)
    momentos = data.pop('momentos_dia', None)
    if data:
        Receta.objects.filter(pk=receta.pk).update(**data)
    receta.refresh_from_db()
    if tipos is not None:
        receta.tipos_receta.set(tipos)
    if momentos is not None:
        receta.momentos_dia.set(momentos)
    RecetaIngrediente.objects.filter(receta=receta).delete()
    for row in formset_cleaned_data:
        if row.get('DELETE'):
            continue
        RecetaIngrediente.objects.create(
            receta=receta,
            ingrediente=row['ingrediente'],
            cantidad=row['cantidad'],
            unidad_medida=row['unidad_medida'],
        )


def planificaciones_que_incluyen_receta(receta):
    """
    Devuelve lista de dicts con planificaciones (menús) que incluyen esta receta.
    Cada dict: fecha, plan_nombre, planificacion_menu_id, momentos (lista de nombres).
    """
    items = PlanificacionMenuReceta.objects.filter(
        receta=receta
    ).select_related(
        'planificacion_menu', 'planificacion_menu__plan', 'tipo_comida'
    ).order_by('planificacion_menu__fecha', 'planificacion_menu__plan__nombre', 'tipo_comida__orden')
    agrupado = defaultdict(list)
    for pmr in items:
        pm = pmr.planificacion_menu
        clave = (pm.fecha, pm.plan.nombre, pm.pk)
        if pmr.tipo_comida.nombre not in agrupado[clave]:
            agrupado[clave].append(pmr.tipo_comida.nombre)
    return [
        {
            'fecha': fecha,
            'plan_nombre': plan_nombre,
            'planificacion_menu_id': menu_id,
            'momentos': momentos,
        }
        for (fecha, plan_nombre, menu_id), momentos in sorted(agrupado.items(), key=lambda x: (x[0][0], x[0][1]))
    ]


def duplicar_receta(receta):
    """
    Duplica una receta (nombre, tipos, momentos, ingredientes y cantidades).
    Devuelve la nueva instancia de Receta.
    """
    nombre_copia = ('Copia de ' + receta.nombre)[:200]
    nueva = Receta.objects.create(
        nombre=nombre_copia,
        descripcion=receta.descripcion or '',
        info_nutricional=dict(receta.info_nutricional) if receta.info_nutricional else {},
        activa=receta.activa,
        producido_en_cocina=receta.producido_en_cocina,
    )
    nueva.tipos_receta.set(receta.tipos_receta.all())
    nueva.momentos_dia.set(receta.momentos_dia.all())
    for ri in receta.receta_ingredientes.select_related('ingrediente', 'unidad_medida').order_by('ingrediente'):
        RecetaIngrediente.objects.create(
            receta=nueva,
            ingrediente=ri.ingrediente,
            cantidad=ri.cantidad,
            unidad_medida=ri.unidad_medida,
        )
    return nueva
