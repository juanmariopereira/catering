"""
Envía recordatorios por WhatsApp a clientes cuyo plan está por vencer
(fecha_fin del contrato dentro de los próximos N días).

Uso:
  python manage.py enviar_recordatorios_vencimiento
  python manage.py enviar_recordatorios_vencimiento --dias 7
  python manage.py enviar_recordatorios_vencimiento --dry-run
"""
from datetime import date, timedelta
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from contracts.models import Contrato, q_filtro_estado
from whatsapp.services.whatsapp_api import send_whatsapp_text, is_whatsapp_configured


def _contratos_por_vencer(dias: int):
    """Contratos activos cuya fecha_fin está entre hoy y hoy + dias (inclusive)."""
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)
    return Contrato.objects.filter(
        q_filtro_estado('activo'),
        fecha_fin__isnull=False,
        fecha_fin__gte=hoy,
        fecha_fin__lte=limite,
    ).select_related('cliente', 'plan')


def _mensaje_recordatorio(cliente_nombre: str, contratos_con_fecha: list[tuple]) -> str:
    """Genera el texto del recordatorio para un cliente."""
    catering = getattr(settings, 'CATERING_NAME', 'Catering Healthy Life')
    lineas = [
        f"Hola {cliente_nombre} 👋",
        "",
        f"Te recordamos desde *{catering}*:",
        "",
    ]
    for contrato, fecha_fin in contratos_con_fecha:
        lineas.append(f"• Tu plan *{contrato.plan.nombre}* vence el *{fecha_fin:%d/%m/%Y}*.")
    lineas.extend([
        "",
        "Para renovar o consultar, respondé por este medio o contactanos.",
        "Gracias.",
    ])
    return "\n".join(lineas)


class Command(BaseCommand):
    help = 'Envía recordatorios por WhatsApp a clientes con plan por vencer.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=5,
            help='Recordar a quienes venzan en los próximos N días (default: 5).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo listar a quiénes se enviaría el recordatorio, sin enviar.',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        dry_run = options['dry_run']

        if not is_whatsapp_configured():
            self.stderr.write(self.style.ERROR(
                'WhatsApp no está configurado (WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID).'
            ))
            return

        contratos = _contratos_por_vencer(dias)
        # Agrupar por cliente
        por_cliente = defaultdict(list)
        for c in contratos:
            por_cliente[c.cliente].append((c, c.fecha_fin))

        enviados = 0
        sin_telefono = 0
        for cliente, contratos_con_fecha in por_cliente.items():
            telefono = (cliente.telefono or '').strip()
            if not telefono:
                sin_telefono += 1
                self.stdout.write(f"  Omitido (sin teléfono): {cliente.nombre}")
                continue
            msg = _mensaje_recordatorio(cliente.nombre, contratos_con_fecha)
            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"  [DRY-RUN] Enviaría a {cliente.nombre} ({telefono})"
                ))
                enviados += 1
                continue
            if send_whatsapp_text(telefono, msg):
                enviados += 1
                self.stdout.write(f"  Enviado: {cliente.nombre}")
            else:
                self.stderr.write(self.style.WARNING(f"  Falló envío: {cliente.nombre}"))

        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {enviados} enviados, {sin_telefono} omitidos (sin teléfono)."
        ))
