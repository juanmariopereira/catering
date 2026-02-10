"""
Lógica de negocio para clientes: listado, detalle y contexto de eliminación.
"""

from django.db.models import Q, Max, Exists, OuterRef

from clients.models import Cliente


ORDER_FIELDS = {
    'nombre': 'nombre',
    '-nombre': '-nombre',
    'email': 'email',
    '-email': '-email',
    'estado': 'activo',
    '-estado': '-activo',
    'ultimo_contrato': 'ultimo_contrato_fecha',
    '-ultimo_contrato': '-ultimo_contrato_fecha',
}


def list_clientes_queryset(*, busqueda=None, activo=None, order=None):
    """
    Devuelve el queryset de clientes filtrado y ordenado.

    Args:
        busqueda: texto para buscar en nombre, email, teléfono
        activo: None = todos, '1' = activos, '0' = inactivos, 'sin_contrato' = sin contrato vigente
        order: clave de orden (ver ORDER_FIELDS)

    Returns:
        QuerySet de Cliente con annotaciones (ultimo_contrato_fecha, tiene_contrato_vigente).
    """
    from contracts.models import Contrato, q_filtro_estado

    queryset = Cliente.objects.all()
    if busqueda:
        queryset = queryset.filter(
            Q(nombre__icontains=busqueda)
            | Q(email__icontains=busqueda)
            | Q(telefono__icontains=busqueda)
        )
    q_vigentes = q_filtro_estado('activo') | q_filtro_estado('pausado') | q_filtro_estado('vencido')
    subq = Contrato.objects.filter(cliente_id=OuterRef('pk')).filter(q_vigentes)
    queryset = queryset.annotate(
        ultimo_contrato_fecha=Max('contratos__fecha_creacion'),
        tiene_contrato_vigente=Exists(subq),
    )
    if activo is not None and activo != '':
        if activo == 'sin_contrato':
            queryset = queryset.filter(tiene_contrato_vigente=False)
        else:
            queryset = queryset.filter(activo=(activo == '1'))
    order_field = ORDER_FIELDS.get((order or 'nombre').strip(), 'nombre')
    return queryset.order_by(order_field)


def get_cliente_detalle_data(cliente):
    """
    Datos para la vista de detalle de un cliente: contratos y cobros pendientes.

    Args:
        cliente: instancia de Cliente

    Returns:
        dict con 'contratos_todos' y 'cobro_pendiente_por_contrato'.
    """
    from django.db.models import Q
    from contracts.models import Contrato
    from billing.models import Cobro

    contratos_todos = (
        Contrato.objects.filter(
            Q(cliente=cliente) | Q(cliente__titular=cliente)
        )
        .select_related('cliente', 'plan')
        .order_by('-fecha_creacion')
    )
    cobro_pendiente_por_contrato = {}
    if contratos_todos:
        ids = [c.pk for c in contratos_todos]
        for c in Cobro.objects.filter(
            contrato_id__in=ids,
            estado__in=['pendiente', 'vencida'],
        ).order_by('contrato_id', 'periodo_desde'):
            if c.contrato_id not in cobro_pendiente_por_contrato:
                cobro_pendiente_por_contrato[c.contrato_id] = c
    return {
        'contratos_todos': contratos_todos,
        'cobro_pendiente_por_contrato': cobro_pendiente_por_contrato,
    }


def get_cliente_delete_context(cliente):
    """
    Contexto para la vista de confirmación de borrado: contratos activos y dependientes con contrato.

    Args:
        cliente: instancia de Cliente

    Returns:
        dict con 'contratos_activos' y 'dependientes_con_contratos_activos'.
    """
    from contracts.models import Contrato, q_filtro_estado

    contratos_activos = (
        Contrato.objects.filter(cliente=cliente)
        .filter(q_filtro_estado('activo'))
        .select_related('plan')
        .order_by('-fecha_creacion')
    )
    contratos_activos_ids = Contrato.objects.filter(q_filtro_estado('activo')).values_list('id', flat=True)
    dependientes_con_contratos_activos = Cliente.objects.filter(
        titular=cliente,
        contratos__in=contratos_activos_ids,
    ).distinct()
    return {
        'contratos_activos': contratos_activos,
        'dependientes_con_contratos_activos': dependientes_con_contratos_activos,
    }


def save_cliente_con_ingredientes_no_gustados(cliente, form_cleaned_data, formset_cleaned_data):
    """
    Actualiza un cliente y sus ingredientes no gustados.
    form_cleaned_data: dict del ClienteForm.
    formset_cleaned_data: lista de dicts del formset (cada uno con ingrediente, motivo, DELETE).
    """
    for key, value in form_cleaned_data.items():
        setattr(cliente, key, value)
    cliente.save()
    # Formset: eliminar los marcados DELETE y crear/actualizar el resto
    from clients.models import IngredienteNoGustado
    IngredienteNoGustado.objects.filter(cliente=cliente).delete()
    for row in formset_cleaned_data:
        if row.get('DELETE') or not row.get('ingrediente'):
            continue
        IngredienteNoGustado.objects.create(
            cliente=cliente,
            ingrediente=row['ingrediente'],
            motivo=row.get('motivo') or '',
        )
