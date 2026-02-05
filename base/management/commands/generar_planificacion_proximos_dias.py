"""
Genera planificación (PlanificacionMenu) para los próximos N días útiles.
Día útil = lunes a viernes, excluyendo feriados.

Por cada día útil y cada plan activo se crea una PlanificacionMenu (fecha, plan)
si no existe. Los menús quedan vacíos; se pueden rellenar después con
"Sugerir menú con IA" o manualmente.

Uso:
  python manage.py generar_planificacion_proximos_dias
  python manage.py generar_planificacion_proximos_dias --dias 15
  python manage.py generar_planificacion_proximos_dias --desde 2025-02-10
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from base.models import es_feriado
from plans.models import Plan
from planning.models import PlanificacionMenu


def proximos_dias_utiles(desde: date, cantidad: int):
    """
    Genera las siguientes `cantidad` días útiles a partir de `desde`.
    Día útil = lunes (0) a viernes (4), no feriado.
    """
    dias = []
    d = desde
    while len(dias) < cantidad:
        if d.weekday() < 5 and not es_feriado(d):
            dias.append(d)
        d += timedelta(days=1)
    return dias


class Command(BaseCommand):
    help = 'Genera planificación (menús por fecha y plan) para los próximos días útiles.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=10,
            help='Número de días útiles a planificar (default: 10).',
        )
        parser.add_argument(
            '--desde',
            type=str,
            default=None,
            help='Fecha de inicio (YYYY-MM-DD). Por defecto: mañana.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        desde_str = options.get('desde')
        if desde_str:
            try:
                desde = date.fromisoformat(desde_str)
            except ValueError:
                self.stderr.write(self.style.ERROR(f'Fecha inválida: {desde_str}. Use YYYY-MM-DD.'))
                return
        else:
            desde = date.today() + timedelta(days=1)  # mañana

        dias = options['dias']
        dias_utiles = proximos_dias_utiles(desde, dias)
        planes = list(Plan.objects.filter(activo=True))
        if not planes:
            self.stdout.write(self.style.WARNING('No hay planes activos. Cree al menos un plan.'))
            return

        creados = 0
        ya_existian = 0
        for d in dias_utiles:
            for plan in planes:
                pm, created = PlanificacionMenu.objects.get_or_create(
                    fecha=d,
                    plan=plan,
                    defaults={},
                )
                if created:
                    creados += 1
                else:
                    ya_existian += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Planificación generada: {len(dias_utiles)} días útiles, {len(planes)} planes. '
                f'Nuevos: {creados}, ya existían: {ya_existian}.'
            )
        )
        self.stdout.write(
            f'Días: {dias_utiles[0].isoformat()} a {dias_utiles[-1].isoformat()}.'
        )
