"""
Servicio para generar mensajes personalizados a clientes con IA.
"""
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List

from django.conf import settings
from django.utils import timezone

from base.ai_logging import extraer_usage, registrar_llamada_ia

logger = logging.getLogger(__name__)

TIPOS_MENSAJE = [
    ('preguntar_dieta', 'Preguntar cómo le ha ido con su dieta'),
    ('plan_por_vencer', 'Avisar que su plan está por vencer'),
    ('plan_vencido', 'Avisar que su plan venció'),
]


def _get_openai_client():
    from openai import OpenAI
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise ValueError('OPENAI_API_KEY no está configurada.')
    return OpenAI(api_key=api_key)


def _obtener_platos_servidos_recientes(contrato, dias: int = 14) -> List[Dict[str, Any]]:
    """
    Obtiene los platos servidos al cliente en los últimos días.
    Devuelve lista de {fecha, momento, receta_nombre}
    """
    from planning.models import PlanificacionMenu, PlanificacionMenuReceta, PlanificacionClienteSustituta, PlanificacionClienteReceta

    hoy = timezone.now().date()
    fecha_desde = hoy - timedelta(days=dias)
    platos = []

    menus = PlanificacionMenu.objects.filter(
        plan=contrato.plan,
        fecha__gte=fecha_desde,
        fecha__lte=hoy,
    ).prefetch_related('recetas__receta', 'recetas__tipo_comida').order_by('fecha')

    sustituciones = PlanificacionClienteSustituta.objects.filter(
        contrato=contrato,
        fecha__gte=fecha_desde,
        fecha__lte=hoy,
    ).select_related('receta_sustituta', 'receta_original', 'tipo_comida')
    sust_map = {(s.fecha, s.tipo_comida_id, s.receta_original_id): s.receta_sustituta.nombre for s in sustituciones}
    personalizaciones = PlanificacionClienteReceta.objects.filter(
        contrato=contrato,
        fecha__gte=fecha_desde,
        fecha__lte=hoy,
    ).order_by('fecha', 'tipo_comida_id', 'orden').select_related('receta')
    from collections import defaultdict
    pers_map = defaultdict(list)
    for s in personalizaciones:
        pers_map[(s.fecha, s.tipo_comida_id)].append(s.receta.nombre)

    for menu in menus:
        if not contrato.activo_en_fecha(menu.fecha):
            continue
        for mr in menu.recetas.all():
            pers_list = pers_map.get((menu.fecha, mr.tipo_comida_id))
            if pers_list:
                for receta_nombre in pers_list:
                    platos.append({
                        'fecha': str(menu.fecha),
                        'momento': mr.tipo_comida.nombre,
                        'receta': receta_nombre,
                    })
            else:
                receta_nombre = sust_map.get(
                    (menu.fecha, mr.tipo_comida_id, mr.receta_id), mr.receta.nombre
                )
                platos.append({
                    'fecha': str(menu.fecha),
                    'momento': mr.tipo_comida.nombre,
                    'receta': receta_nombre,
                })

    return platos


def generar_mensaje_cliente_ia(contrato, tipo_mensaje: str, request=None) -> str:
    """
    Genera un mensaje personalizado para el cliente según el tipo.

    Args:
        contrato: instancia de Contrato
        tipo_mensaje: 'preguntar_dieta' | 'plan_por_vencer' | 'plan_vencido'
        request: opcional para registrar usuario

    Returns:
        Mensaje de texto personalizado (para WhatsApp, email, etc.)
    """
    if tipo_mensaje not in [t[0] for t in TIPOS_MENSAJE]:
        raise ValueError(f'Tipo de mensaje inválido: {tipo_mensaje}')

    client = _get_openai_client()

    cliente_nombre = contrato.cliente.nombre
    plan_nombre = contrato.plan.nombre
    fecha_inicio = contrato.fecha_inicio.strftime('%d/%m/%Y') if contrato.fecha_inicio else '—'
    fecha_fin = contrato.fecha_fin.strftime('%d/%m/%Y') if contrato.fecha_fin else None

    contexto_platos = ''
    if tipo_mensaje == 'preguntar_dieta':
        platos = _obtener_platos_servidos_recientes(contrato)
        if platos:
            por_fecha = {}
            for p in platos:
                f = p['fecha']
                if f not in por_fecha:
                    por_fecha[f] = []
                por_fecha[f].append(f"{p['momento']}: {p['receta']}")
            lineas = []
            for f in sorted(por_fecha.keys(), reverse=True)[:7]:
                lineas.append(f"  {f}: " + "; ".join(por_fecha[f]))
            contexto_platos = "\nPlatos servidos recientemente:\n" + "\n".join(lineas)
        else:
            contexto_platos = "\n(No hay registros de platos servidos en los últimos 14 días.)"

    system_prompt = """Eres un asistente de un servicio de catering de comida saludable.
Generas mensajes breves, cordiales y personalizados para clientes.
El tono es cercano pero profesional. Los mensajes deben ser adecuados para WhatsApp o email.
Escribe en español. Solo el texto del mensaje, sin encabezado ni firma (el usuario lo añadirá si quiere).
IMPORTANTE: Usa SIEMPRE los datos concretos que te proporciono (fechas, nombres de platos, plan) para personalizar el mensaje."""

    if tipo_mensaje == 'preguntar_dieta':
        user_prompt = f"""Cliente: {cliente_nombre}
Plan: {plan_nombre}
{contexto_platos}

Genera un mensaje breve para preguntarle al cliente cómo le ha ido últimamente con su dieta.
DEBE mencionar algunos de los platos concretos que le hemos servido (usa los de la lista).
Invítale a dar su opinión o feedback."""
    elif tipo_mensaje == 'plan_por_vencer':
        user_prompt = f"""Cliente: {cliente_nombre}
Plan: {plan_nombre}
Fecha de vencimiento: {fecha_fin}

Genera un mensaje breve para avisarle que su plan está por vencer.
DEBE incluir la fecha exacta de vencimiento ({fecha_fin}) en el mensaje.
Menciona el nombre del plan ({plan_nombre}) y el nombre del cliente ({cliente_nombre}).
Invítale a renovar o contactar para continuar."""
    else:  # plan_vencido
        user_prompt = f"""Cliente: {cliente_nombre}
Plan: {plan_nombre}
Fecha en que venció: {fecha_fin}

Genera un mensaje breve para avisarle que su plan ha vencido.
DEBE incluir la fecha de vencimiento ({fecha_fin}) y el nombre del plan ({plan_nombre}).
Invítale a renovar para seguir disfrutando del servicio."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
            timeout=60.0,
        )
        u = extraer_usage(response)
        registrar_llamada_ia(
            accion='generar_mensaje_cliente',
            modelo='gpt-4o-mini',
            objeto_tipo='contrato',
            objeto_id=contrato.pk,
            usuario=getattr(request, 'user', None) if request else None,
            **u,
        )
        content = (response.choices[0].message.content or '').strip()
        return content
    except Exception as e:
        registrar_llamada_ia(
            accion='generar_mensaje_cliente',
            modelo='gpt-4o-mini',
            exito=False,
            mensaje_error=str(e),
            objeto_tipo='contrato',
            objeto_id=contrato.pk,
            usuario=getattr(request, 'user', None) if request else None,
        )
        logger.warning('Error al generar mensaje cliente %s: %s', contrato.pk, e)
        raise
