"""
Persiste en HistoricoAsignacionEntrega la asignación contrato → entregador por fecha,
según el estado actual de las plantillas y contratos con entrega ese día.
Pensado para ejecutarse diariamente vía crontab (ej. a las 23:00 o 06:00).

Uso:
  python manage.py persistir_historico_entregas
  python manage.py persistir_historico_entregas --fecha 2026-02-10
  python manage.py persistir_historico_entregas --fecha ayer

Crontab (ejemplo, todos los días a las 23:00):
  0 23 * * * cd /ruta/al/proyecto && python manage.py persistir_historico_entregas >> /var/log/catering_historico_entregas.log 2>&1
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from contracts.models import Contrato
from delivery.utils import entregador_por_contrato_en_fecha
from planning.models import PlanificacionMenu
from routes.models import HistoricoAsignacionEntrega


class Command(BaseCommand):
    help = (
        'Persiste en HistoricoAsignacionEntrega la asignación contrato-entregador por fecha '
        'según plantillas y contratos con entrega ese día. Para crontab diario.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fecha',
            type=str,
            default=None,
            help='Fecha (YYYY-MM-DD). Por defecto: hoy. Use "ayer" para el día anterior.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fecha_str = options.get('fecha')
        if fecha_str:
            if fecha_str.strip().lower() == 'ayer':
                fecha = date.today() - timedelta(days=1)
            else:
                try:
                    fecha = date.fromisoformat(fecha_str.strip())
                except ValueError:
                    self.stderr.write(self.style.ERROR(f'Fecha inválida: {fecha_str}'))
                    return
        else:
            fecha = date.today()

        entregador_por_contrato = entregador_por_contrato_en_fecha(fecha)
        if not entregador_por_contrato:
            self.stdout.write(
                self.style.WARNING(f'{fecha}: No hay contratos con entrega asignada (o es feriado).')
            )
            return

        contratos = {
            c.id: c for c in Contrato.objects.filter(id__in=entregador_por_contrato.keys()).select_related('plan')
        }
        menus_por_plan = {
            pm.plan_id: pm
            for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
        }

        creados = 0
        actualizados = 0
        for contrato_id, entregador in entregador_por_contrato.items():
            contrato = contratos.get(contrato_id)
            if not contrato:
                continue
            planificacion_menu = menus_por_plan.get(contrato.plan_id) if contrato.plan_id else None

            obj, created = HistoricoAsignacionEntrega.objects.update_or_create(
                fecha=fecha,
                contrato_id=contrato_id,
                defaults={
                    'entregador': entregador,
                    'planificacion_menu': planificacion_menu,
                },
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{fecha}: {creados} creados, {actualizados} actualizados '
                f'(total {len(entregador_por_contrato)} asignaciones).'
            )
        )
