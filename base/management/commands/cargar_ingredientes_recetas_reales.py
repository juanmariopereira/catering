"""
Comando para eliminar todos los ingredientes y recetas actuales y cargar
500 ingredientes reales (con información nutricional y alérgenos) y
1000 recetas reales (con tipos, momentos, info nutricional e ingredientes).

Uso:
  python manage.py cargar_ingredientes_recetas_reales

Elimina también las referencias a recetas/ingredientes en otras apps
(PlanificacionMenuReceta, PlanificacionClienteSustituta, DietaReceta,
PrevisionCompraItem, IngredienteNoGustado). No borra UnidadMedida, TipoReceta,
TipoComida ni clientes, contratos, planes, etc.
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        'Elimina todos los ingredientes y recetas y carga 500 ingredientes reales '
        'y 1000 recetas reales (con información nutricional, alérgenos, etc.).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría, sin borrar ni crear.',
        )

    def _permite_ejecutar(self):
        if getattr(settings, 'ALLOW_LOAD_TEST_DATA', False):
            return True
        if getattr(settings, 'DEBUG', False):
            return True
        return False

    @transaction.atomic
    def handle(self, *args, **options):
        if not self._permite_ejecutar():
            raise CommandError(
                'Este comando es solo para desarrollo (DEBUG=True) o con '
                'ALLOW_LOAD_TEST_DATA=True en la configuración.'
            )
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write('Modo dry-run: no se modificará la base de datos.')

        from recipes.models import RecetaIngrediente, Receta, Ingrediente, TipoReceta, UnidadMedida
        from diets.models import TipoComida, DietaReceta
        from planning.models import PlanificacionMenuReceta, PlanificacionClienteSustituta
        from clients.models import IngredienteNoGustado
        from purchases.models import PrevisionCompraItem

        # 1. Borrar en orden de dependencias (referencias a Receta e Ingrediente)
        if not dry_run:
            PlanificacionMenuReceta.objects.all().delete()
            PlanificacionClienteSustituta.objects.all().delete()
            DietaReceta.objects.all().delete()
            PrevisionCompraItem.objects.all().delete()
            IngredienteNoGustado.objects.all().delete()
            count_ri = RecetaIngrediente.objects.count()
            count_r = Receta.objects.count()
            count_i = Ingrediente.objects.count()
            RecetaIngrediente.objects.all().delete()
            Receta.objects.all().delete()
            Ingrediente.objects.all().delete()
            self.stdout.write(f'Eliminados: PlanificacionMenuReceta, PlanificacionClienteSustituta, DietaReceta, PrevisionCompraItem, IngredienteNoGustado; {count_ri} RecetaIngrediente, {count_r} Receta, {count_i} Ingrediente.')
        else:
            self.stdout.write(
                f'Se eliminarían: RecetaIngrediente ({RecetaIngrediente.objects.count()}), '
                f'Receta ({Receta.objects.count()}), Ingrediente ({Ingrediente.objects.count()}).'
            )
            return

        # 2. Asegurar UnidadMedida (gr, kg, lt, un)
        unidades_data = [
            ('Gramo', 'gr', 1),
            ('Kilogramo', 'kg', 2),
            ('Litro', 'lt', 3),
            ('Unidad', 'un', 4),
        ]
        um_by_simbolo = {}
        for nombre_um, simbolo, orden in unidades_data:
            um, _ = UnidadMedida.objects.get_or_create(
                nombre=nombre_um,
                defaults={'simbolo': simbolo, 'orden': orden, 'activo': True}
            )
            um_by_simbolo[simbolo] = um

        # 3. Asegurar TipoComida (momentos del día)
        momentos_data = [
            ('Desayuno', 1),
            ('Media mañana', 2),
            ('Comida', 3),
            ('Merienda', 4),
            ('Cena', 5),
        ]
        tc_by_nombre = {}
        for nombre, orden in momentos_data:
            tc, _ = TipoComida.objects.get_or_create(
                nombre=nombre,
                defaults={'orden': orden}
            )
            tc_by_nombre[nombre] = tc

        # 4. Asegurar TipoReceta
        tipos_receta_data = [
            ('Comida', 1),
            ('Masa', 2),
            ('Postre', 3),
            ('Complemento', 4),
            ('Bebida', 5),
            ('Fruta', 6),
        ]
        tr_by_nombre = {}
        for nombre, orden in tipos_receta_data:
            tr, _ = TipoReceta.objects.get_or_create(
                nombre=nombre,
                defaults={'orden': orden, 'activo': True}
            )
            tr_by_nombre[nombre] = tr

        # 5. Cargar 500 ingredientes
        from recipes.data.ingredientes_500 import get_ingredientes
        ingredientes_data = get_ingredientes()
        ing_by_nombre = {}
        for d in ingredientes_data:
            unidad = um_by_simbolo.get(d['unidad']) or um_by_simbolo['gr']
            info_nutri = {'por_100g': d['por_100g']}
            ing = Ingrediente.objects.create(
                nombre=d['nombre'],
                unidad_medida=unidad,
                info_nutricional=info_nutri,
                alergenos=d.get('alergenos') or [],
                activo=True,
            )
            ing_by_nombre[d['nombre']] = ing
        self.stdout.write(self.style.SUCCESS(f'Creados {len(ing_by_nombre)} ingredientes.'))

        # 6. Cargar 1000 recetas
        from recipes.data.recetas_1000 import get_recetas
        recetas_data = get_recetas()
        created = 0
        skipped_ing = 0
        for d in recetas_data:
            rec = Receta.objects.create(
                nombre=d['nombre'],
                descripcion=d.get('descripcion') or '',
                info_nutricional=d.get('info_nutricional') or {},
                activa=True,
                producido_en_cocina=True,
            )
            rec.tipos_receta.set([tr_by_nombre[t] for t in d['tipos'] if t in tr_by_nombre])
            rec.momentos_dia.set([tc_by_nombre[m] for m in d['momentos'] if m in tc_by_nombre])
            for ing_item in d.get('ingredientes') or []:
                nombre_ing = ing_item.get('ingrediente')
                ing_obj = ing_by_nombre.get(nombre_ing)
                if not ing_obj:
                    skipped_ing += 1
                    continue
                cantidad = ing_item.get('cantidad', 0.1)
                try:
                    cantidad = Decimal(str(cantidad))
                except Exception:
                    cantidad = Decimal('0.1')
                unidad_sim = ing_item.get('unidad', 'gr')
                um = um_by_simbolo.get(unidad_sim) or um_by_simbolo['gr']
                RecetaIngrediente.objects.create(
                    receta=rec,
                    ingrediente=ing_obj,
                    cantidad=cantidad,
                    unidad_medida=um,
                )
            created += 1
            if created % 200 == 0:
                self.stdout.write(f'  Recetas creadas: {created}...')
        if skipped_ing:
            self.stdout.write(self.style.WARNING(f'Referencias a ingredientes no encontrados: {skipped_ing}'))
        self.stdout.write(self.style.SUCCESS(f'Creadas {created} recetas con sus ingredientes.'))
