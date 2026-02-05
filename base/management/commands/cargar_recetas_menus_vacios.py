"""
Asigna múltiples recetas a todos los menús planificados (PlanificacionMenu) que
no tengan al menos una receta. Por cada momento del día (Desayuno, Media mañana,
Comida, Merienda, Cena) se asignan 1 o 2 recetas aptas para ese momento.

Uso:
  python manage.py cargar_recetas_menus_vacios
  python manage.py cargar_recetas_menus_vacios --dry-run   # solo mostrar qué menús se rellenarían
  python manage.py cargar_recetas_menus_vacios --max-por-momento 1   # 1 receta por momento (default 2)
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from planning.models import PlanificacionMenu, PlanificacionMenuReceta
from diets.models import TipoComida
from recipes.models import Receta


class Command(BaseCommand):
    help = 'Carga recetas en los menús planificados que no tienen ninguna receta.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué menús se rellenarían, sin crear registros.',
        )
        parser.add_argument(
            '--max-por-momento',
            type=int,
            default=2,
            help='Máximo de recetas por momento del día (default: 2).',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=123,
            help='Semilla para aleatoriedad reproducible (default: 123).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        max_por_momento = max(1, min(5, options['max_por_momento']))
        seed = options['seed']

        # Menús con cero recetas
        menus_vacios = PlanificacionMenu.objects.annotate(
            num_recetas=Count('recetas')
        ).filter(num_recetas=0).select_related('plan').order_by('fecha', 'plan')

        menus_vacios = list(menus_vacios)
        if not menus_vacios:
            self.stdout.write(self.style.SUCCESS('No hay menús sin recetas.'))
            return

        tipos_comida = list(TipoComida.objects.order_by('orden', 'nombre'))
        if not tipos_comida:
            self.stdout.write(self.style.WARNING('No hay tipos de comida (momentos del día). Cree Desayuno, Media mañana, etc. en Dietas.'))
            return

        recetas_activas = list(Receta.objects.filter(activa=True).prefetch_related('momentos_dia').order_by('nombre'))
        if not recetas_activas:
            self.stdout.write(self.style.WARNING('No hay recetas activas.'))
            return

        # Por tipo_comida: lista de recetas aptas (con ese momento en momentos_dia, o todas si ninguna tiene)
        recetas_por_momento = {}
        for tc in tipos_comida:
            aptas = [r for r in recetas_activas if tc in r.momentos_dia.all()]
            if not aptas:
                aptas = recetas_activas
            recetas_por_momento[tc.id] = aptas

        random.seed(seed)
        creados_total = 0

        if dry_run:
            self.stdout.write(f'Se asignarían recetas a {len(menus_vacios)} menú(s) vacío(s):')
            for pm in menus_vacios[:10]:
                self.stdout.write(f'  - {pm.fecha} | {pm.plan.nombre}')
            if len(menus_vacios) > 10:
                self.stdout.write(f'  ... y {len(menus_vacios) - 10} más.')
            self.stdout.write(self.style.WARNING('Ejecute sin --dry-run para crear las recetas en cada menú.'))
            return

        with transaction.atomic():
            for pm in menus_vacios:
                random.seed(seed + pm.id * 1000)  # variedad por menú
                for tc in tipos_comida:
                    aptas = list(recetas_por_momento.get(tc.id, recetas_activas))
                    if not aptas:
                        continue
                    random.shuffle(aptas)
                    n = min(max_por_momento, len(aptas))
                    elegidas = aptas[:n]
                    for orden, receta in enumerate(elegidas, start=1):
                        _, created = PlanificacionMenuReceta.objects.get_or_create(
                            planificacion_menu=pm,
                            tipo_comida=tc,
                            receta=receta,
                            defaults={'orden': orden},
                        )
                        if created:
                            creados_total += 1

        self.stdout.write(self.style.SUCCESS(
            f'Asignadas {creados_total} receta(s) en {len(menus_vacios)} menú(s) que estaban vacíos.'
        ))
