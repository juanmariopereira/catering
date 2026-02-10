"""
Lógica de negocio para contratos: listado, detalle, días extra.

Puede ser consumida por vistas web y por futuras API REST (app móvil).
"""

from datetime import date as date_type, timedelta

from django.db.models import Q, Case, When, Value, IntegerField, Exists, OuterRef, Min, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction

from contracts.models import Contrato, ExtensionVigencia, q_filtro_estado
from billing.models import Cobro, _dias_vencimiento_por_frecuencia


def parse_sort(sort_param):
    """'cliente:desc,plan:asc' -> [('cliente', 'desc'), ('plan', 'asc')]"""
    result = []
    if not sort_param or not sort_param.strip():
        return result
    valid_cols = {'cliente', 'plan', 'estado', 'vencimiento', 'fecha_inicio', 'precio'}
    for part in sort_param.strip().split(','):
        part = part.strip()
        if ':' in part:
            col, dir_ = part.split(':', 1)
            col, dir_ = col.strip(), dir_.strip().lower()
            if col in valid_cols and dir_ in ('asc', 'desc'):
                result.append((col, dir_))
    return result


def next_sort(current_parsed, column):
    """Ciclo: (ninguno) -> desc -> asc -> (ninguno). Devuelve (nueva_lista, nueva_dirección_para_columna)."""
    current_dir = next((d for c, d in current_parsed if c == column), None)
    if current_dir == 'desc':
        new_parsed = [(c, 'asc' if c == column else d) for c, d in current_parsed]
        return new_parsed, 'asc'
    if current_dir == 'asc':
        new_parsed = [(c, d) for c, d in current_parsed if c != column]
        return new_parsed, None
    new_parsed = current_parsed + [(column, 'desc')]
    return new_parsed, 'desc'


def sort_to_string(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


SORTABLE_COLUMNS = [
    ('cliente', 'Cliente'),
    ('plan', 'Plan'),
    ('fecha_inicio', 'Fecha Inicio'),
    ('vencimiento', 'Fecha vencimiento'),
    ('precio', 'Precio'),
    ('estado', 'Estado'),
]


def list_contratos_queryset(
    *,
    busqueda=None,
    estado=None,
    plan_id=None,
    cliente_id=None,
    vencimiento_desde=None,
    vencimiento_hasta=None,
    sort_param=None,
):
    """
    Devuelve el queryset de contratos filtrado y ordenado.

    Args:
        busqueda: texto para buscar en nombre cliente o plan
        estado: filtro de estado (activo, vencido, etc.)
        plan_id, cliente_id: filtros por FK
        vencimiento_desde, vencimiento_hasta: filtro por fecha_fin
        sort_param: string tipo 'cliente:desc,plan:asc'

    Returns:
        QuerySet de Contrato (con select_related cliente, plan).
    """
    queryset = Contrato.objects.all()
    if busqueda:
        queryset = queryset.filter(
            Q(cliente__nombre__icontains=busqueda) | Q(plan__nombre__icontains=busqueda)
        )
    if estado:
        queryset = queryset.filter(q_filtro_estado(estado))
    if plan_id:
        queryset = queryset.filter(plan_id=plan_id)
    if cliente_id:
        queryset = queryset.filter(cliente_id=cliente_id)
    if vencimiento_desde:
        queryset = queryset.filter(fecha_fin__gte=vencimiento_desde)
    if vencimiento_hasta:
        queryset = queryset.filter(fecha_fin__lte=vencimiento_hasta)
    queryset = queryset.select_related('cliente', 'plan')

    sort_parsed = parse_sort(sort_param or '')
    hoy = timezone.now().date()

    if not sort_parsed:
        limite_pre = hoy + timedelta(days=5)
        cobro_vigente = Cobro.objects.filter(contrato_id=OuterRef('pk'), periodo_hasta__gte=hoy)
        cobros_pendientes = Cobro.objects.filter(
            contrato_id=OuterRef('pk'),
            estado__in=['pendiente', 'vencida'],
        )
        queryset = queryset.annotate(
            tiene_cobro_vigente=Exists(cobro_vigente),
            tiene_cobros_pendientes=Exists(cobros_pendientes),
            min_vencimiento=Min(
                'cobros__fecha_vencimiento',
                filter=Q(cobros__estado__in=['pendiente', 'vencida']),
            ),
        )
        queryset = queryset.annotate(
            estado_orden_default=Case(
                When(fecha_cancelacion__isnull=False, then=Value(3)),
                When(fecha_pausa__isnull=False, fecha_reanudacion__isnull=True, then=Value(3)),
                When(
                    Q(fecha_fin__isnull=False) & Q(fecha_fin__lt=hoy) & Q(tiene_cobro_vigente=False),
                    then=Value(3),
                ),
                When(tiene_cobros_pendientes=True, then=Value(0)),
                When(
                    Q(fecha_cancelacion__isnull=True)
                    & (Q(fecha_pausa__isnull=True) | Q(fecha_reanudacion__isnull=False))
                    & Q(fecha_fin__isnull=False)
                    & Q(fecha_fin__gte=hoy)
                    & Q(fecha_fin__lte=limite_pre)
                    & Q(fecha_inicio__lte=hoy),
                    then=Value(1),
                ),
                default=Value(2),
                output_field=IntegerField(),
            ),
        )
        queryset = queryset.annotate(
            orden_vencimiento=Coalesce(F('min_vencimiento'), Value(date_type(9999, 12, 31))),
        )
        return queryset.order_by('estado_orden_default', 'orden_vencimiento', '-fecha_creacion')

    sort_columns = [c for c, _ in sort_parsed]
    if 'estado' in sort_columns:
        limite_pre = hoy + timedelta(days=5)
        cobro_vigente = Cobro.objects.filter(contrato_id=OuterRef('pk'), periodo_hasta__gte=hoy)
        cobros_pendientes = Cobro.objects.filter(
            contrato_id=OuterRef('pk'),
            estado__in=['pendiente', 'vencida'],
        )
        queryset = queryset.annotate(
            tiene_cobro_vigente=Exists(cobro_vigente),
            tiene_cobros_pendientes=Exists(cobros_pendientes),
        )
        queryset = queryset.annotate(
            estado_orden=Case(
                When(fecha_cancelacion__isnull=False, then=Value(0)),
                When(fecha_pausa__isnull=False, fecha_reanudacion__isnull=True, then=Value(0)),
                When(
                    Q(fecha_fin__isnull=False) & Q(fecha_fin__lt=hoy) & Q(tiene_cobro_vigente=False),
                    then=Value(0),
                ),
                When(tiene_cobros_pendientes=True, then=Value(3)),
                When(
                    Q(fecha_cancelacion__isnull=True)
                    & (Q(fecha_pausa__isnull=True) | Q(fecha_reanudacion__isnull=False))
                    & Q(fecha_fin__isnull=False)
                    & Q(fecha_fin__gte=hoy)
                    & Q(fecha_fin__lte=limite_pre)
                    & Q(fecha_inicio__lte=hoy),
                    then=Value(2),
                ),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
    order_by_list = []
    for col, dir_ in sort_parsed:
        prefix = '' if dir_ == 'asc' else '-'
        if col == 'cliente':
            order_by_list.append(f'{prefix}cliente__nombre')
        elif col == 'plan':
            order_by_list.append(f'{prefix}plan__nombre')
        elif col == 'fecha_inicio':
            order_by_list.append(f'{prefix}fecha_inicio')
        elif col == 'vencimiento':
            order_by_list.append(f'{prefix}fecha_fin')
        elif col == 'precio':
            order_by_list.append(f'{prefix}precio')
        elif col == 'estado':
            order_by_list.append(f'{prefix}estado_orden')
    order_by_list.append('-fecha_creacion')
    return queryset.order_by(*order_by_list)


def get_contrato_detalle_data(contrato):
    """
    Datos para la vista de detalle de un contrato: pausas y cobros.

    Returns:
        dict con 'pausas' y 'cobros'.
    """
    pausas = contrato.pausas.all().order_by('-fecha_inicio')
    cobros = (
        Cobro.objects.filter(contrato=contrato)
        .prefetch_related('pagos')
        .order_by('-periodo_hasta', '-numero_cobro')
    )
    return {'pausas': pausas, 'cobros': cobros}


def get_contrato_list_context(get_params, *, per_page_current, per_page_options):
    """
    Contexto para la lista de contratos: planes, clientes, query_string, sort_headers, etc.
    """
    from plans.models import Plan
    from clients.models import Cliente

    get_copy = get_params.copy()
    if 'page' in get_copy:
        get_copy.pop('page')
    get_no_sort = get_params.copy()
    get_no_sort.pop('sort', None)
    get_no_sort.pop('page', None)
    sort_parsed = parse_sort(get_params.get('sort', ''))
    sort_headers = []
    for col_key, col_label in SORTABLE_COLUMNS:
        next_parsed, _ = next_sort(sort_parsed, col_key)
        next_sort_str = sort_to_string(next_parsed) if next_parsed else ''
        current_dir = next((d for c, d in sort_parsed if c == col_key), None)
        sort_headers.append({
            'sortable': True,
            'key': col_key,
            'label': col_label,
            'direction': current_dir,
            'next_sort': next_sort_str,
        })
    table_headers = [
        sort_headers[0], sort_headers[1], sort_headers[2], sort_headers[3], sort_headers[4], sort_headers[5],
        {'sortable': False, 'label': 'Coordenadas'},
        {'sortable': False, 'label': 'Acciones'},
    ]
    return {
        'planes': Plan.objects.filter(activo=True).order_by('nombre'),
        'clientes': Cliente.objects.order_by('nombre'),
        'query_string': get_copy.urlencode(),
        'query_base_no_sort': get_no_sort.urlencode(),
        'sort_headers': sort_headers,
        'table_headers': table_headers,
        'per_page_current': per_page_current,
        'per_page_options': per_page_options,
    }


def get_contrato_create_initial(plan_id=None):
    """Initial para formulario de creación de contrato (plan y precio por defecto)."""
    from plans.models import Plan

    initial = {}
    if plan_id:
        try:
            plan = Plan.objects.get(pk=plan_id, activo=True)
            initial['plan'] = plan.pk
            initial['precio'] = plan.precio_base
        except Plan.DoesNotExist:
            pass
    return initial


def get_contrato_create_context():
    """Contexto para formulario de creación: plan_precios y clientes_datos."""
    from plans.models import Plan
    from clients.models import Cliente

    return {
        'plan_precios': {str(p.id): str(p.precio_base) for p in Plan.objects.filter(activo=True)},
        'clientes_datos': {
            str(c.id): {'direccion': c.direccion or '', 'link_maps': c.link_maps or ''}
            for c in Cliente.objects.all()
        },
    }


def get_cliente_direccion_data(cliente):
    """Datos de dirección de un cliente para JSON (formulario contrato)."""
    return {
        'direccion': cliente.direccion or '',
        'link_maps': cliente.link_maps or '',
        'latitud': str(cliente.latitud) if cliente.latitud is not None else '',
        'longitud': str(cliente.longitud) if cliente.longitud is not None else '',
    }


def get_ultimo_contrato_direccion_data(cliente, exclude_contrato_pk=None):
    """
    Dirección del último contrato activo del cliente (para copiar en nuevo contrato).
    exclude_contrato_pk: opcional, excluir ese contrato del resultado.
    """
    qs = Contrato.objects.filter(cliente=cliente).filter(q_filtro_estado('activo'))
    if exclude_contrato_pk is not None:
        try:
            qs = qs.exclude(pk=int(exclude_contrato_pk))
        except (ValueError, TypeError):
            pass
    ultimo = qs.order_by('-fecha_creacion').first()
    if not ultimo:
        return {
            'direccion_entrega': '',
            'link_maps': '',
            'latitud': '',
            'longitud': '',
        }
    return {
        'direccion_entrega': ultimo.direccion_entrega or '',
        'link_maps': ultimo.link_maps or '',
        'latitud': str(ultimo.latitud) if ultimo.latitud is not None else '',
        'longitud': str(ultimo.longitud) if ultimo.longitud is not None else '',
    }


def aplicar_dias_extra(contrato, dias_agregados, motivo):
    """
    Extiende la vigencia del contrato y del último cobro añadiendo días.
    Crea un registro en ExtensionVigencia.

    Raises:
        ValueError: si el contrato está cancelado.
    """
    if contrato.estado == 'cancelado':
        raise ValueError('No se pueden dar días extra a un contrato cancelado.')
    hoy = timezone.now().date()
    ultimo_cobro = contrato.cobros.order_by('-periodo_hasta').first()
    base_fin = contrato.fecha_fin or (ultimo_cobro.periodo_hasta if ultimo_cobro else hoy)
    nueva_fecha_fin = base_fin + timedelta(days=dias_agregados)
    with transaction.atomic():
        Contrato.objects.filter(pk=contrato.pk).update(fecha_fin=nueva_fecha_fin)
        if ultimo_cobro:
            ultimo_cobro.periodo_hasta = nueva_fecha_fin
            ultimo_cobro.fecha_vencimiento = nueva_fecha_fin + timedelta(
                days=_dias_vencimiento_por_frecuencia(contrato.frecuencia_pago)
            )
            ultimo_cobro.save(update_fields=['periodo_hasta', 'fecha_vencimiento'])
        ExtensionVigencia.objects.create(
            contrato=contrato,
            dias_agregados=dias_agregados,
            motivo=motivo,
        )
