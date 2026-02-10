from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.forms import inlineformset_factory
from datetime import date, timedelta
from collections import defaultdict
from .models import (
    PlanificacionMenu,
    PlanificacionMenuReceta,
    PlanificacionClienteSustituta,
    PlanificacionClienteReceta,
)
from .forms import PlanificacionMenuForm, PlanificacionMenuRecetaForm
from .utils import (
    obtener_conflictos_menu_por_cliente_con_precarga,
    recetas_alternativas_para_momento_con_precarga,
    clientes_no_gustan_por_receta,
    dieta_etiqueta_contrato,
    obtener_ingredientes_no_gustados_por_clientes,
    obtener_ingredientes_por_recetas,
)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from contracts.models import Contrato, contratos_activos_en_fecha, q_filtro_estado
from base.models import es_feriado, get_feriado
from delivery.utils import contratos_en_ruta_fecha, entregador_por_contrato_en_fecha
from diets.models import TipoComida
from plans.models import Plan
from recipes.models import Receta, Ingrediente
from routes.models import Entregador
from .services.ai_menu import sugerir_menu_ia

BasePlanificacionMenuRecetaFormSet = inlineformset_factory(
    PlanificacionMenu,
    PlanificacionMenuReceta,
    form=PlanificacionMenuRecetaForm,
    fields=('tipo_comida', 'receta', 'orden'),
    extra=1,
    can_delete=True,
)


class PlanificacionMenuRecetaFormSet(BasePlanificacionMenuRecetaFormSet):
    """Formset que pasa receta_counts al form para mostrar [N] clientes en el select."""

    def __init__(self, *args, receta_counts=None, **kwargs):
        self.receta_counts = receta_counts or {}
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['receta_counts'] = self.receta_counts
        return kwargs


@login_required
def resumen_por_fecha(request):
    """
    Cantidad de clientes por plan en una fecha específica.
    Sirve para saber cuántos clientes hay por dieta/plan antes de crear las planificaciones.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    # Contratos activos en esa fecha (estado activo, en rango, sin pausa ese día)
    contratos_fecha = contratos_activos_en_fecha(fecha).select_related('plan', 'cliente')

    # Agrupar por plan: plan -> [contratos]
    por_plan = defaultdict(list)
    for c in contratos_fecha:
        por_plan[c.plan].append(c)

    # PlanificacionMenu por (fecha, plan) para enlazar Editar/Crear menú
    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    # Lista de (plan, cantidad, contratos, planificacion_menu) para el template (dieta no utilizada por ahora)
    resumen = []
    for plan in Plan.objects.filter(activo=True).order_by('nombre'):
        contratos = por_plan.get(plan, [])
        planificacion_menu = menus_por_plan.get(plan.id)
        resumen.append({
            'plan': plan,
            'cantidad': len(contratos),
            'contratos': contratos,
            'planificacion_menu': planificacion_menu,
        })

    # Avisos pendientes: clientes con ingredientes no deseados en el menú (para resumen rápido)
    avisos_pendientes = 0
    for r in resumen:
        if not r['planificacion_menu'] or not r['contratos']:
            continue
        for c in r['contratos']:
            if obtener_conflictos_menu_por_cliente(r['planificacion_menu'], c):
                avisos_pendientes += 1
    fecha_anterior = fecha - timedelta(days=1)
    fecha_siguiente = fecha + timedelta(days=1)

    context = {
        'fecha': fecha,
        'resumen': resumen,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
        'total_clientes': sum(r['cantidad'] for r in resumen),
        'menus_creados': len([r for r in resumen if r['planificacion_menu']]),
        'avisos_pendientes': avisos_pendientes,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }
    return render(request, 'planning/resumen_por_fecha.html', context)


VIGENCIA_CHOICES = [
    ('', 'Todos (en vigencia)'),
    ('activo', 'Activo'),
    ('pre_renovacion', 'Pre-Renovación'),
    ('pausado', 'Pausado'),
    ('vencido', 'Vencido'),
    ('cancelado', 'Cancelado'),
]


@login_required
def clientes_reciben_fecha(request):
    """
    Lista de clientes por plan que recibirán sus comidas en una fecha.
    Filtros: plan, entregador, cliente (texto), vigencia del contrato.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    # Parámetros de filtro
    filtro_plan = request.GET.get('plan', '').strip()
    filtro_entregador = request.GET.get('entregador', '').strip()
    filtro_cliente = request.GET.get('cliente', '').strip()
    filtro_vigencia = request.GET.get('vigencia', '').strip()

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

    # Aplicar filtros en memoria (plan, entregador, cliente)
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

    planes_opciones = [(str(pid), nombre) for pid, nombre in Plan.objects.filter(id__in=plan_ids_con_menu, activo=True).order_by('nombre').values_list('id', 'nombre')]
    entregadores_opciones = [(str(eid), nombre) for eid, nombre in Entregador.objects.filter(activo=True).order_by('nombre').values_list('id', 'nombre')]

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

    context = {
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
    return render(request, 'planning/clientes_reciben_fecha.html', context)


@login_required
def contratos_sin_entregador_fecha(request):
    """
    Detalle de contratos que reciben menú en la fecha pero no tienen repartidor asignado.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    contratos_fecha = contratos_activos_en_fecha(fecha).select_related('plan', 'cliente')
    contrato_ids_con_ruta = contratos_en_ruta_fecha(fecha)
    filas_sin_entregador = []
    for c in contratos_fecha:
        if c.plan_id not in menus_por_plan or c.id in contrato_ids_con_ruta:
            continue
        filas_sin_entregador.append({
            'contrato': c,
            'cliente': c.cliente,
            'plan': c.plan,
        })

    context = {
        'fecha': fecha,
        'filas': filas_sin_entregador,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }
    return render(request, 'planning/contratos_sin_entregador_fecha.html', context)


@login_required
@require_http_methods(['POST'])
def sugerir_menu_ia_view(request):
    """
    Vista AJAX que sugiere un menú usando OpenAI.
    POST: fecha (YYYY-MM-DD), plan (ID)
    Returns: JSON { "ok": true, "recetas": [{ tipo_comida_id, receta_id, orden }] } o { "ok": false, "error": "..." }
    """
    fecha_str = request.POST.get('fecha')
    plan_id_str = request.POST.get('plan')

    if not fecha_str or not plan_id_str:
        return JsonResponse({'ok': False, 'error': 'Faltan fecha o plan.'}, status=400)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida.'}, status=400)

    try:
        plan_id = int(plan_id_str)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Plan inválido.'}, status=400)

    plan = get_object_or_404(Plan, pk=plan_id)
    idea_menu = (request.POST.get('idea_menu') or '').strip() or None

    try:
        recetas = sugerir_menu_ia(fecha, plan, request=request, idea_menu=idea_menu)
        return JsonResponse({'ok': True, 'recetas': recetas})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse(
            {'ok': False, 'error': f'Error al generar sugerencia: {e}'},
            status=500,
        )


def _parse_sort_planning(sort_param):
    """'fecha:desc,plan:asc' -> [('fecha', 'desc'), ('plan', 'asc')]"""
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


def _sort_to_string_planning(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


SORTABLE_COLUMNS_PLANNING = [
    ('fecha', 'Fecha'),
    ('plan', 'Plan'),
]


class PlanificacionMenuListView(LoginRequiredMixin, ListView):
    """Lista de planificaciones por fecha y plan (menús)."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_lista.html'
    context_object_name = 'planificaciones'
    paginate_by = 30

    def get_queryset(self):
        queryset = PlanificacionMenu.objects.all().select_related('plan')
        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            try:
                fd = date.fromisoformat(fecha_desde)
                queryset = queryset.filter(fecha__gte=fd)
            except ValueError:
                pass
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            try:
                fh = date.fromisoformat(fecha_hasta)
                queryset = queryset.filter(fecha__lte=fh)
            except ValueError:
                pass
        plan_id = self.request.GET.get('plan')
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        sort_parsed = _parse_sort_planning(self.request.GET.get('sort', ''))
        if not sort_parsed:
            return queryset.order_by('-fecha', 'plan__nombre')
        order_by_list = []
        for col, dir_ in sort_parsed:
            prefix = '' if dir_ == 'asc' else '-'
            if col == 'fecha':
                order_by_list.append(f'{prefix}fecha')
            elif col == 'plan':
                order_by_list.append(f'{prefix}plan__nombre')
        order_by_list.extend(['-fecha', 'plan__nombre'])
        return queryset.order_by(*order_by_list)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['planes'] = Plan.objects.filter(activo=True).order_by('nombre')
        get_copy = self.request.GET.copy()
        if 'page' in get_copy:
            get_copy.pop('page')
        context['query_string'] = get_copy.urlencode()
        get_no_sort = self.request.GET.copy()
        get_no_sort.pop('sort', None)
        get_no_sort.pop('page', None)
        context['query_base_no_sort'] = get_no_sort.urlencode()
        sort_parsed = _parse_sort_planning(self.request.GET.get('sort', ''))
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
        context['table_headers'] = [
            sort_headers[0],
            sort_headers[1],
            {'sortable': False, 'label': 'Acciones'},
        ]
        return context


class PlanificacionMenuCreateView(LoginRequiredMixin, CreateView):
    """Crear menú planificado (fecha + plan). Una sola planificación por (fecha, plan)."""
    model = PlanificacionMenu
    form_class = PlanificacionMenuForm
    template_name = 'planning/planificacion_menu_form.html'
    success_url = reverse_lazy('planning:lista')

    def get(self, request, *args, **kwargs):
        """Si ya existe planificación para esta fecha y plan, redirigir a editar esa."""
        fecha_param = request.GET.get('fecha')
        plan_param = request.GET.get('plan')
        if fecha_param and plan_param:
            try:
                fecha = date.fromisoformat(fecha_param)
                existente = PlanificacionMenu.objects.filter(fecha=fecha, plan_id=plan_param).first()
                if existente:
                    messages.info(
                        request,
                        f'Ya existe una planificación para el {fecha.strftime("%d/%m/%Y")} con ese plan. Redirigido a edición.'
                    )
                    return redirect(reverse('planning:editar', args=[existente.pk]))
            except (ValueError, TypeError):
                pass
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        fecha_param = self.request.GET.get('fecha')
        plan_id = self.request.GET.get('plan')
        if fecha_param:
            try:
                initial['fecha'] = date.fromisoformat(fecha_param)
            except ValueError:
                initial['fecha'] = timezone.now().date() + timedelta(days=1)
        else:
            initial['fecha'] = timezone.now().date() + timedelta(days=1)
        if plan_id:
            initial['plan'] = plan_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['planes'] = Plan.objects.filter(activo=True).order_by('nombre')
        initial = self.get_initial()
        fecha = initial.get('fecha')
        plan = initial.get('plan')
        receta_counts = clientes_no_gustan_por_receta(fecha, plan) if (fecha and plan) else {}
        if self.request.POST:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                self.request.POST, instance=self.object, receta_counts=receta_counts
            )
        else:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                instance=self.object, receta_counts=receta_counts
            )
        return context

    def form_valid(self, form):
        self.object = form.save()
        fecha = self.object.fecha
        plan = self.object.plan
        receta_counts = clientes_no_gustan_por_receta(fecha, plan)
        receta_formset = PlanificacionMenuRecetaFormSet(
            self.request.POST, instance=self.object, receta_counts=receta_counts
        )
        if receta_formset.is_valid():
            receta_formset.save()
            messages.success(
                self.request,
                'Menú creado con las recetas por momento del día. Puede editar sustituciones por cliente si lo necesita.'
            )
        else:
            messages.warning(
                self.request,
                'Menú creado. Revise las recetas a continuación y guarde de nuevo si hizo cambios.'
            )
        return redirect(reverse('planning:editar', args=[self.object.pk]))


class PlanificacionMenuUpdateView(LoginRequiredMixin, UpdateView):
    """Editar menú: recetas por tipo_comida (formset) y sustituciones por cliente."""
    model = PlanificacionMenu
    form_class = PlanificacionMenuForm
    template_name = 'planning/planificacion_menu_form.html'
    success_url = reverse_lazy('planning:lista')
    context_object_name = 'planificacion_menu'

    def get_queryset(self):
        return PlanificacionMenu.objects.select_related('plan')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        fecha = obj.fecha
        plan = obj.plan
        receta_counts = clientes_no_gustan_por_receta(fecha, plan)
        if self.request.POST:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                self.request.POST, instance=obj, receta_counts=receta_counts
            )
        else:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                instance=obj, receta_counts=receta_counts
            )
        # Contratos activos en esta fecha con este plan (una query, en memoria)
        contratos = list(
            contratos_activos_en_fecha(fecha).filter(plan=plan).select_related('cliente')
        )
        context['contratos_fecha'] = contratos
        contrato_ids = [c.id for c in contratos]
        cliente_ids = [c.cliente_id for c in contratos]

        # Sustituciones actuales (una query)
        sustituciones_actuales = {}
        for row in PlanificacionClienteSustituta.objects.filter(
            fecha=fecha, contrato_id__in=contrato_ids
        ).values_list('contrato_id', 'tipo_comida_id', 'receta_original_id', 'receta_sustituta_id'):
            sustituciones_actuales[(row[0], row[1], row[2])] = row[3]

        # Recetas del menú con receta y tipo_comida (una query + prefetch tipos_receta)
        menu_recetas = list(
            PlanificacionMenuReceta.objects.filter(planificacion_menu=obj)
            .select_related('receta', 'tipo_comida')
            .prefetch_related('receta__tipos_receta')
            .order_by('tipo_comida__orden', 'orden')
        )
        receta_ids_menu = [mr.receta_id for mr in menu_recetas]

        # Recetas activas (una query, para "todas" y para alternativas)
        recetas_todas = list(Receta.objects.filter(activa=True).order_by('nombre'))
        receta_ids_activas = [r.id for r in recetas_todas]

        # Ingredientes no gustados por cliente (una query batch)
        ingredientes_no_gustados_por_cliente = obtener_ingredientes_no_gustados_por_clientes(cliente_ids)

        # Ingredientes por receta para menu + todas activas (dos queries batch)
        receta_ingredientes = obtener_ingredientes_por_recetas(receta_ids_menu)
        receta_ingredientes.update(
            obtener_ingredientes_por_recetas(receta_ids_activas)
        )
        all_ing_ids = set()
        for ing_set in receta_ingredientes.values():
            all_ing_ids |= ing_set
        for ing_set in ingredientes_no_gustados_por_cliente.values():
            all_ing_ids |= ing_set
        ingredientes_por_id = Ingrediente.objects.in_bulk(all_ing_ids) if all_ing_ids else {}

        # Tipos de comida en el menú (desde menu_recetas, sin query)
        tipos_en_menu_ids = list({mr.tipo_comida_id for mr in menu_recetas})
        tipos_en_menu = list(
            TipoComida.objects.filter(id__in=tipos_en_menu_ids).order_by('orden', 'nombre')
        )
        context['tiene_momentos_en_menu'] = bool(tipos_en_menu)

        # Recetas por tipo_comida para alternativas (una query por tipo en menú, con prefetch tipos_receta)
        recetas_por_tipo_comida = {}
        for tcid in tipos_en_menu_ids:
            recetas_por_tipo_comida[tcid] = list(
                Receta.objects.filter(activa=True, momentos_dia=tcid)
                .prefetch_related('tipos_receta')
                .order_by('nombre')
            )

        # Conflictos y alternativas por contrato (tod0 en memoria)
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

        context['clientes_conflictos'] = clientes_conflictos
        context['recetas_todas'] = recetas_todas
        context['show_dietas_personalizadas'] = True
        context['tipos_para_anadir'] = tipos_en_menu

        # Lista de excepciones (una query)
        lista_excepciones = list(
            PlanificacionClienteReceta.objects.filter(
                fecha=fecha, contrato_id__in=contrato_ids
            ).select_related('contrato__cliente', 'tipo_comida', 'receta', 'receta_original').order_by(
                'contrato__cliente__nombre', 'tipo_comida__orden', 'orden'
            )
        )
        context['lista_excepciones'] = lista_excepciones
        context['contratos_para_anadir'] = [(c.id, c.cliente.nombre) for c in contratos]
        return context

    def form_valid(self, form):
        form.save()
        self._guardar_sustituciones_cliente()
        self._guardar_dietas_personalizadas()
        context = self.get_context_data(form=form)
        receta_formset = context['receta_formset']
        if receta_formset.is_valid():
            receta_formset.save()
            messages.success(self.request, 'Menú actualizado correctamente.')
            return redirect(self.get_success_url())
        messages.warning(
            self.request,
            'Menú y excepciones guardados. Revise los errores en «Recetas por momento del día» y guarde de nuevo si hace falta.'
        )
        return self.render_to_response(context)

    def _guardar_sustituciones_cliente(self):
        """Guardar PlanificacionClienteSustituta desde POST sustituir_contrato_X_tipo_Y_receta_Z."""
        for key in self.request.POST:
            if not key.startswith('sustituir_contrato_'):
                continue
            # sustituir_contrato_3_tipo_1_receta_5 -> contrato 3, tipo 1, receta 5
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
            fecha = self.object.fecha
            receta_sustituta_id = self.request.POST.get(key, '').strip()
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

    def _guardar_dietas_personalizadas(self):
        """Guardar: quitar excepciones (quitar_id) y añadir las nuevas (nuevo_N_contrato, nuevo_N_tipo_comida, nuevo_N_receta_original, nuevo_N_receta)."""
        fecha = self.object.fecha
        # Quitar las marcadas
        quitar_ids = []
        for v in self.request.POST.getlist('quitar_id'):
            try:
                quitar_ids.append(int(v))
            except (ValueError, TypeError):
                pass
        if quitar_ids:
            PlanificacionClienteReceta.objects.filter(
                pk__in=quitar_ids, fecha=fecha
            ).delete()
        # Añadir todas las filas nuevas enviadas
        try:
            total = int(self.request.POST.get('nuevo_excepciones_total', 1))
        except (ValueError, TypeError):
            total = 1
        for i in range(total):
            nuevo_contrato = self.request.POST.get('nuevo_%s_contrato' % i, '').strip()
            nuevo_tipo = self.request.POST.get('nuevo_%s_tipo_comida' % i, '').strip()
            nuevo_receta_original = self.request.POST.get('nuevo_%s_receta_original' % i, '').strip()
            nuevo_receta = self.request.POST.get('nuevo_%s_receta' % i, '').strip()
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


class PlanificacionMenuDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar planificación menú (fecha + plan)."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_confirm_delete.html'
    success_url = reverse_lazy('planning:lista')
    context_object_name = 'planificacion_menu'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Menú eliminado.')
        return super().delete(request, *args, **kwargs)


@login_required
def calendario_planificacion(request, year=None, month=None):
    """Vista para mostrar calendario de planificaciones"""
    if year and month:
        try:
            fecha = date(int(year), int(month), 1)
        except ValueError:
            fecha = timezone.now().date().replace(day=1)
    else:
        fecha = timezone.now().date().replace(day=1)
    
    # Calcular primer y último día del mes
    if fecha.month == 12:
        siguiente_mes = fecha.replace(year=fecha.year + 1, month=1)
    else:
        siguiente_mes = fecha.replace(month=fecha.month + 1)
    
    ultimo_dia = (siguiente_mes - timedelta(days=1)).day
    # Día de la semana del 1 (0=lunes, 6=domingo): celdas vacías antes del día 1
    primer_dia_mes = fecha.replace(day=1)
    celdas_vacias_inicio = primer_dia_mes.weekday()
    dias_del_mes = list(range(1, ultimo_dia + 1))
    # Siempre 6 filas (42 celdas) para que el calendario no cambie de altura al cambiar de mes
    TOTAL_CELDAS_MES = 6 * 7
    celdas_vacias_fin = TOTAL_CELDAS_MES - celdas_vacias_inicio - ultimo_dia
    rango_vacias_inicio = list(range(celdas_vacias_inicio))
    rango_vacias_fin = list(range(max(0, celdas_vacias_fin)))

    # Menús planificados por fecha (PlanificacionMenu)
    planificaciones = PlanificacionMenu.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month
    ).select_related('plan')

    planificaciones_por_dia = {}
    for planificacion in planificaciones:
        dia = planificacion.fecha.day
        if dia not in planificaciones_por_dia:
            planificaciones_por_dia[dia] = []
        planificaciones_por_dia[dia].append(planificacion)

    # Feriados del mes (día -> nombre) para marcar en el calendario
    from base.models import Feriado
    feriados_mes = Feriado.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month,
    )
    feriados_por_dia = {f.fecha.day: f.nombre for f in feriados_mes}
    
    # Calcular mes anterior y siguiente
    if fecha.month == 1:
        mes_anterior = fecha.replace(year=fecha.year - 1, month=12)
    else:
        mes_anterior = fecha.replace(month=fecha.month - 1)
    
    context = {
        'fecha': fecha,
        'mes_anterior': mes_anterior,
        'mes_siguiente': siguiente_mes,
        'ultimo_dia': ultimo_dia,
        'celdas_vacias_inicio': celdas_vacias_inicio,
        'celdas_vacias_fin': celdas_vacias_fin,
        'rango_vacias_inicio': rango_vacias_inicio,
        'rango_vacias_fin': rango_vacias_fin,
        'dias_del_mes': dias_del_mes,
        'planificaciones_por_dia': planificaciones_por_dia,
        'feriados_por_dia': feriados_por_dia,
    }
    
    return render(request, 'planning/calendario.html', context)


@login_required
@require_http_methods(['GET'])
def recetas_por_tipo_ajax(request):
    """AJAX: devuelve recetas activas filtradas por tipo de comida (momentos_dia)."""
    tipo_id = request.GET.get('tipo_comida_id', '').strip()
    if not tipo_id:
        return JsonResponse({'recetas': []})
    try:
        tipo_id = int(tipo_id)
    except ValueError:
        return JsonResponse({'recetas': []})
    recetas = list(
        Receta.objects.filter(
            activa=True,
            momentos_dia__id=tipo_id,
        ).order_by('nombre').values_list('id', 'nombre')
    )
    return JsonResponse({
        'recetas': [{'id': r[0], 'nombre': r[1]} for r in recetas],
    })


@login_required
@require_http_methods(['GET'])
def recetas_del_menu_ajax(request):
    """AJAX: devuelve recetas del menú de una planificación para un tipo de comida."""
    planificacion_id = request.GET.get('planificacion_id', '').strip()
    tipo_id = request.GET.get('tipo_comida_id', '').strip()
    if not planificacion_id or not tipo_id:
        return JsonResponse({'recetas': []})
    try:
        planificacion_id = int(planificacion_id)
        tipo_id = int(tipo_id)
    except ValueError:
        return JsonResponse({'recetas': []})
    menu = get_object_or_404(PlanificacionMenu, pk=planificacion_id)
    recetas = list(
        PlanificacionMenuReceta.objects.filter(
            planificacion_menu=menu,
            tipo_comida_id=tipo_id,
        ).select_related('receta').order_by('orden').values_list('receta_id', 'receta__nombre')
    )
    return JsonResponse({
        'recetas': [{'id': r[0], 'nombre': r[1]} for r in recetas],
    })


@login_required
def etiqueta_dieta(request, planificacion_id, contrato_id):
    """
    Vista para imprimir la etiqueta de la dieta enviada a un cliente.
    Contiene: logo, nombre empresa, fecha, plan, cliente, platos por tipo de comida, info nutricional.
    """
    planificacion = get_object_or_404(PlanificacionMenu, pk=planificacion_id)
    contrato = get_object_or_404(
        Contrato.objects.select_related('cliente', 'plan'),
        pk=contrato_id,
    )
    if contrato.plan_id != planificacion.plan_id:
        messages.warning(request, 'El contrato no corresponde al plan de esta planificación.')
        return redirect('planning:lista')
    data = dieta_etiqueta_contrato(planificacion, contrato)
    if not data:
        messages.warning(request, 'No hay datos de dieta para este cliente en esta fecha.')
        return redirect('planning:lista')
    return render(request, 'planning/etiqueta_dieta.html', data)


@login_required
@require_http_methods(['GET'])
def etiquetas_dieta_masivo(request):
    """
    Impresión masiva: una sola página con todas las etiquetas seleccionadas.
    GET ids: planificacion_id/contrato_id separados por coma (ej. ids=27/132,27/133,27/134).
    """
    ids_param = request.GET.get('ids', '').strip()
    if not ids_param:
        messages.warning(request, 'No se indicaron etiquetas.')
        return redirect('planning:clientes_por_fecha')
    etiquetas = []
    for part in ids_param.split(','):
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
    if not etiquetas:
        messages.warning(request, 'No hay etiquetas válidas para mostrar.')
        return redirect('planning:clientes_por_fecha')
    return render(request, 'planning/etiquetas_dieta_masivo.html', {'etiquetas': etiquetas})
