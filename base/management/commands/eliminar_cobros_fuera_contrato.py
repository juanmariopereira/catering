"""
Elimina cobros cuyo rango de fechas (periodo_desde, periodo_hasta) está fuera
del rango del contrato correspondiente (fecha_inicio, fecha_fin).

Criterios de eliminación:
- periodo_desde < contrato.fecha_inicio (el cobro empieza antes del contrato)
- periodo_hasta > contrato.fecha_fin cuando el contrato tiene fecha_fin (el cobro termina después del contrato)

Uso:
  python manage.py eliminar_cobros_fuera_contrato
  python manage.py eliminar_cobros_fuera_contrato --dry-run   # solo listar, no borrar
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, F

from billing.models import Cobro


class Command(BaseCommand):
    help = 'Elimina cobros cuyo período está fuera del rango de fechas del contrato.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué cobros se eliminarían, sin borrar.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Cobros que empiezan antes del inicio del contrato
        # o terminan después del fin del contrato (si el contrato tiene fecha_fin)
        fuera_rango = Cobro.objects.filter(
            Q(periodo_desde__lt=F('contrato__fecha_inicio'))
            | Q(
                contrato__fecha_fin__isnull=False,
                periodo_hasta__gt=F('contrato__fecha_fin'),
            )
        ).select_related('contrato', 'contrato__cliente')

        count = fuera_rango.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No hay cobros fuera del rango del contrato.'))
            return

        if dry_run:
            self.stdout.write(f'Se encontrarían {count} cobro(s) fuera del rango del contrato:')
            for cobro in fuera_rango[:50]:
                self.stdout.write(
                    f'  - {cobro.numero_cobro or cobro.pk} | {cobro.contrato.cliente.nombre} | '
                    f'período {cobro.periodo_desde} a {cobro.periodo_hasta} | '
                    f'contrato {cobro.contrato.fecha_inicio} a {cobro.contrato.fecha_fin or "—"}'
                )
            if count > 50:
                self.stdout.write(f'  ... y {count - 50} más.')
            self.stdout.write(self.style.WARNING('Ejecute sin --dry-run para eliminar.'))
            return

        # Eliminar (los Pagos se eliminan en cascada)
        deleted = fuera_rango.delete()
        # deleted is (total_count, {model: count})
        total = deleted[0]
        self.stdout.write(self.style.SUCCESS(f'Eliminados {total} registro(s) ({count} cobro(s) y sus pagos asociados).'))
