"""
Lógica de negocio para listado de clientes que reciben menú en una fecha.
"""

from datetime import date, timedelta
from urllib.parse import urlencode

from django.utils import timezone
from django.db.models import Q

from planning.models import PlanificacionMenu
from planning.utils import obtener_conflictos_menu_por_cliente
from contracts.models import Contrato, contratos_activos_en_fecha, q_filtro_estado
from delivery.utils import contratos_en_ruta_fecha, entregador_por_contrato_en_fecha
from plans.models import Plan
from routes.models import Entregador
from base.models import es_feriado, get_feriado


VIGENCIA_CHOICES = [
    ('', 'Todos (en vigencia)'),
    ('activo', 'Activo'),
    ('pre_renovacion', 'Pre-Renovación'),
    ('pausado', 'Pausado'),
    ('vencido', 'Vencido'),
    ('cancelado', 'Cancelado'),
]


def get_clientes_reciben_fecha(
    fecha=None,
    *,
    filtro_plan=None,
    filtro_entregador=None,
    filtro_cliente=None,
    filtro_vigencia=None,
):
    """
    Lista de clientes/contratos que reciben menú en la fecha, con filtros.

    Returns:
        dict con: fecha, filas (lista de {plan, contrato, cliente, planificacion_menu,
        tiene_aviso, conflictos_count, sin_entregador, entregador}), cantidad_sin_entregador,
        fecha_anterior, fecha_siguiente, es_feriado, feriado, planes_opciones,
        entregadores_opciones, vigencia_choices, y funciones query_filtros para URLs.
    """
    if fecha is None:
        fecha = timezone.now().date()
    filtro_plan = (filtro_plan or '').strip()
    filtro_entregador = (filtro_entregador or '').strip()
    filtro_cliente = (filtro_cliente or '').strip()
    filtro_vigencia = (filtro_vigencia or '').strip()

    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    plan_ids_con_menu = list(menus_por_plan.keys())

    if filtro_vigencia and filtro_vigencia != 'activo':
        contratos_fecha = (
            Contrato.objects.filter(fecha_inicio__lte=fecha)
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
            .exclude(
                pausas__fecha_inicio__lte=fecha,
                pausas__fecha_fin__gte=fecha,
            )
            .filter(plan_id__in=plan_ids_con_menu)
            .filter(q_filtro_estado(filtro_vigencia))
            .distinct()
            .select_related('plan', 'cliente')
        )
    else:
        contratos_fecha = (
            contratos_activos_en_fecha(fecha)
            .filter(plan_id__in=plan_ids_con_menu)
            .select_related('plan', 'cliente')
        )

    contrato_ids_con_ruta = contratos_en_ruta_fecha(fecha)
    entregador_por_contrato = entregador_por_contrato_en_fecha(fecha)

    filas = []
    for c in contratos_fecha:
        menu = menus_por_plan.get(c.plan_id)
        if not menu:
            continue
        conflictos = obtener_conflictos_menu_por_cliente(menu, c)
        tiene_aviso = len(conflictos) > 0
        sin_entregador = c.id not in contrato_ids_con_ruta
        ent = entregador_por_contrato.get(c.id)
        filas.append({
            'plan': c.plan,
            'contrato': c,
            'cliente': c.cliente,
            'planificacion_menu': menu,
            'tiene_aviso': tiene_aviso,
            'conflictos_count': len(conflictos),
            'sin_entregador': sin_entregador,
            'entregador': ent,
        })

    if filtro_plan:
        try:
            plan_id = int(filtro_plan)
            filas = [f for f in filas if f['plan'].id == plan_id]
        except ValueError:
            pass
    if filtro_entregador:
        if filtro_entregador == 'sin':
            filas = [f for f in filas if f['sin_entregador']]
        else:
            try:
                ent_id = int(filtro_entregador)
                filas = [f for f in filas if f['entregador'] and f['entregador'].id == ent_id]
            except ValueError:
                pass
    if filtro_cliente:
        q = filtro_cliente.lower()
        filas = [f for f in filas if q in (f['cliente'].nombre or '').lower()]

    cantidad_sin_entregador = sum(1 for f in filas if f['sin_entregador'])
    fecha_anterior = fecha - timedelta(days=1)
    fecha_siguiente = fecha + timedelta(days=1)

    planes_opciones = list(
        Plan.objects.filter(id__in=plan_ids_con_menu, activo=True)
        .order_by('nombre')
        .values_list('id', 'nombre')
    )
    planes_opciones = [(str(pid), nombre) for pid, nombre in planes_opciones]
    entregadores_opciones = list(
        Entregador.objects.filter(activo=True).order_by('nombre').values_list('id', 'nombre')
    )
    entregadores_opciones = [(str(eid), nombre) for eid, nombre in entregadores_opciones]

    def _query_filtros(override_fecha=None):
        p = {}
        p['fecha'] = (override_fecha or fecha).strftime('%Y-%m-%d')
        if filtro_plan:
            p['plan'] = filtro_plan
        if filtro_entregador:
            p['entregador'] = filtro_entregador
        if filtro_cliente:
            p['cliente'] = filtro_cliente
        if filtro_vigencia:
            p['vigencia'] = filtro_vigencia
        return urlencode(p)

    return {
        'fecha': fecha,
        'filas': filas,
        'cantidad_sin_entregador': cantidad_sin_entregador,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
        'filtro_plan': filtro_plan,
        'filtro_entregador': filtro_entregador,
        'filtro_cliente': filtro_cliente,
        'filtro_vigencia': filtro_vigencia,
        'planes_opciones': planes_opciones,
        'entregadores_opciones': entregadores_opciones,
        'vigencia_choices': VIGENCIA_CHOICES,
        'query_filtros': _query_filtros(),
        'query_filtros_anterior': _query_filtros(fecha_anterior),
        'query_filtros_siguiente': _query_filtros(fecha_siguiente),
    }
