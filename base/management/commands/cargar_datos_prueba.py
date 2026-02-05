"""
Comando para cargar datos de prueba en todas las tablas del sistema de catering.
Solo para desarrollo: en producción (DEBUG=False) el comando se niega a ejecutarse.
Los datos de prueba no se cargan en migraciones; solo bajo demanda con este comando.

Uso en desarrollo:
  python manage.py cargar_datos_prueba
  python manage.py cargar_datos_prueba --flush   (borra datos existentes antes)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def _cargar_recetas_bebidas_postres_frutas(Receta, TipoReceta, tipo_receta_objs):
    """Crea 50 recetas de catálogo: bebidas, postres y frutas (solo bajo demanda)."""
    bebidas = [
        'Agua', 'Café', 'Té verde', 'Té negro', 'Infusión manzanilla',
        'Zumo naranja', 'Zumo manzana', 'Batido fresa', 'Batido plátano',
        'Limonada', 'Granizado limón', 'Horchata', 'Cacao', 'Cola',
        'Tónica', 'Agua con gas', 'Té rojo',
    ]
    postres = [
        'Flan', 'Natillas', 'Arroz con leche', 'Tarta de queso', 'Brownie',
        'Mousse chocolate', 'Tiramisú', 'Crema catalana', 'Yogur natural',
        'Helado vainilla', 'Tarta manzana', 'Bizcocho', 'Coulant',
        'Tarta zanahoria', 'Pudín', 'Gelatina frutas', 'Macedonia',
    ]
    frutas = [
        'Manzana', 'Pera', 'Plátano', 'Naranja', 'Mandarina', 'Uvas',
        'Sandía', 'Melón', 'Kiwi', 'Fresas', 'Cerezas', 'Piña',
        'Mango', 'Melocotón', 'Ciruela', 'Granada',
    ]
    for nombre in bebidas:
        rec, created = Receta.objects.get_or_create(nombre=nombre, defaults={'activa': True})
        if created and 'Bebida' in tipo_receta_objs:
            rec.tipos_receta.add(tipo_receta_objs['Bebida'])
    for nombre in postres:
        rec, created = Receta.objects.get_or_create(nombre=nombre, defaults={'activa': True})
        if created and 'Postre' in tipo_receta_objs:
            rec.tipos_receta.add(tipo_receta_objs['Postre'])
    for nombre in frutas:
        rec, created = Receta.objects.get_or_create(nombre=nombre, defaults={'activa': True})
        if created and 'Fruta' in tipo_receta_objs:
            rec.tipos_receta.add(tipo_receta_objs['Fruta'])


class Command(BaseCommand):
    help = 'Carga datos de prueba en todas las tablas del catering (solo desarrollo).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Eliminar datos existentes antes de cargar (opcional).',
        )

    def _permite_ejecutar(self):
        """Solo permitir en desarrollo (DEBUG=True) o si ALLOW_LOAD_TEST_DATA está activo."""
        if getattr(settings, 'ALLOW_LOAD_TEST_DATA', False):
            return True
        if getattr(settings, 'DEBUG', False):
            return True
        return False

    @transaction.atomic
    def handle(self, *args, **options):
        if not self._permite_ejecutar():
            raise CommandError(
                'Este comando es solo para desarrollo. No se ejecutará en producción '
                '(DEBUG=False). Para permitirlo en otro entorno, defina ALLOW_LOAD_TEST_DATA=True '
                'en su configuración.'
            )
        if options['flush']:
            self._flush_data()
        self._load_data()
        self.stdout.write(self.style.SUCCESS('Datos de prueba cargados correctamente.'))

    def _flush_data(self):
        """Elimina datos en orden inverso de dependencias."""
        from billing.models import Pago, Factura
        from purchases.models import PrevisionCompraItem, PrevisionCompra
        from kitchen.models import DetalleCocina
        from planning.models import PlanificacionClienteSustituta, PlanificacionMenuReceta, PlanificacionMenu
        from routes.models import RutaCliente, Ruta, Entregador
        from diets.models import DietaReceta, Dieta
        from contracts.models import Contrato
        from clients.models import IngredienteNoGustado, Cliente
        from plans.models import Plan
        from recipes.models import RecetaIngrediente, Receta, Ingrediente, TipoReceta, UnidadMedida
        from diets.models import TipoComida

        Pago.objects.all().delete()
        Factura.objects.all().delete()
        PrevisionCompraItem.objects.all().delete()
        PrevisionCompra.objects.all().delete()
        DetalleCocina.objects.all().delete()
        PlanificacionClienteSustituta.objects.all().delete()
        PlanificacionMenuReceta.objects.all().delete()
        PlanificacionMenu.objects.all().delete()
        RutaCliente.objects.all().delete()
        Ruta.objects.all().delete()
        Entregador.objects.all().delete()
        DietaReceta.objects.all().delete()
        for d in Dieta.objects.all():
            d.planes.clear()
        Dieta.objects.all().delete()
        Contrato.objects.all().delete()
        IngredienteNoGustado.objects.all().delete()
        Cliente.objects.all().delete()
        Plan.objects.all().delete()
        RecetaIngrediente.objects.all().delete()
        Receta.objects.all().delete()
        TipoReceta.objects.all().delete()
        Ingrediente.objects.all().delete()
        UnidadMedida.objects.all().delete()
        TipoComida.objects.all().delete()
        self.stdout.write('Datos existentes eliminados.')

    def _load_data(self):
        from diets.models import TipoComida, Dieta, DietaReceta
        from recipes.models import Ingrediente, Receta, RecetaIngrediente, TipoReceta, UnidadMedida
        from plans.models import Plan
        from clients.models import Cliente, IngredienteNoGustado
        from contracts.models import Contrato
        from routes.models import Entregador, Ruta, RutaCliente
        from planning.models import PlanificacionMenu, PlanificacionMenuReceta, PlanificacionClienteSustituta
        from kitchen.models import DetalleCocina
        from billing.models import Factura, Pago
        from purchases.models import PrevisionCompra, PrevisionCompraItem

        hoy = date.today()

        # 1. Tipos de comida (diets)
        tipos = [
            ('Desayuno', 1), ('Media mañana', 2), ('Comida', 3), ('Merienda', 4), ('Cena', 5),
        ]
        tipo_objs = {}
        for nombre, orden in tipos:
            tc, _ = TipoComida.objects.get_or_create(nombre=nombre, defaults={'orden': orden})
            tipo_objs[nombre] = tc

        # 2. Unidades de medida (recipes)
        unidades_data = [
            ('Kilogramo', 'kg', 1), ('Gramo', 'gr', 2), ('Litro', 'lt', 3), ('Unidad', 'un', 4),
        ]
        um_objs = {}
        for nombre_um, simbolo, orden in unidades_data:
            um, _ = UnidadMedida.objects.get_or_create(nombre=nombre_um, defaults={'simbolo': simbolo, 'orden': orden})
            um_objs[simbolo] = um
        # Ingredientes: 100 total (20 con nombre + 80 genéricos)
        ingredientes_base = [
            ('Tomate', 'kg'), ('Lechuga', 'kg'), ('Pollo', 'kg'), ('Arroz', 'kg'), ('Aceite', 'lt'),
            ('Sal', 'gr'), ('Pimienta', 'gr'), ('Cebolla', 'kg'), ('Zanahoria', 'kg'), ('Huevo', 'un'),
            ('Leche', 'lt'), ('Harina', 'kg'), ('Azúcar', 'kg'), ('Manzana', 'kg'), ('Plátano', 'kg'),
            ('Pimiento', 'kg'), ('Ajo', 'gr'), ('Limón', 'un'), ('Queso', 'kg'), ('Pan', 'un'),
        ]
        unidades_ciclo = ['kg', 'gr', 'lt', 'un']
        ing_objs = {}
        for nombre, unidad_simbolo in ingredientes_base:
            um = um_objs.get(unidad_simbolo) or um_objs['un']
            ing, _ = Ingrediente.objects.get_or_create(nombre=nombre, defaults={'unidad_medida': um})
            ing_objs[nombre] = ing
        for i in range(len(ingredientes_base) + 1, 101):
            nombre = f'Ingrediente {i}'
            um = um_objs[unidades_ciclo[(i - 1) % 4]]
            ing, _ = Ingrediente.objects.get_or_create(nombre=nombre, defaults={'unidad_medida': um})
            ing_objs[nombre] = ing

        # 2b. Tipos de receta (recipes)
        tipos_receta_data = [
            ('Comida', 1), ('Masa', 2), ('Postre', 3), ('Complemento', 4), ('Bebida', 5), ('Fruta', 6),
        ]
        tipo_receta_objs = {}
        for nombre, orden in tipos_receta_data:
            tr, _ = TipoReceta.objects.get_or_create(nombre=nombre, defaults={'orden': orden})
            tipo_receta_objs[nombre] = tr

        # 3. Recetas: 100 total (15 con datos + 85 genéricas)
        recetas_data = [
            ('Ensalada mixta', ['Comida', 'Complemento'], ['Desayuno', 'Comida']),
            ('Pechuga a la plancha', ['Comida'], ['Comida']),
            ('Arroz con verduras', ['Comida'], ['Comida']),
            ('Sopa de pollo', ['Comida'], ['Comida']),
            ('Tortilla de huevos', ['Comida'], ['Desayuno']),
            ('Yogur con frutas', ['Complemento', 'Fruta'], ['Media mañana', 'Merienda']),
            ('Sándwich integral', ['Comida', 'Complemento'], ['Cena']),
            ('Pasta al pesto', ['Comida'], ['Comida']),
            ('Crema de zanahoria', ['Comida'], ['Comida']),
            ('Fruta fresca', ['Fruta'], ['Media mañana', 'Merienda']),
            ('Té con galletas', ['Bebida', 'Complemento'], ['Media mañana', 'Merienda']),
            ('Batido de plátano', ['Bebida', 'Fruta'], ['Desayuno']),
            ('Pollo al horno', ['Comida'], ['Cena']),
            ('Ensalada César', ['Comida'], ['Comida', 'Cena']),
            ('Pan con aceite', ['Complemento'], ['Desayuno']),
        ]
        tipos_default = ['Comida']
        momentos_default = ['Comida']
        rec_objs = {}
        for nombre, tipos_keys, momentos_keys in recetas_data:
            rec, _ = Receta.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': f'Receta de {nombre}'}
            )
            rec.tipos_receta.set([tipo_receta_objs[k] for k in tipos_keys])
            rec.momentos_dia.set([tipo_objs[k] for k in momentos_keys])
            rec_objs[nombre] = rec
        for i in range(len(recetas_data) + 1, 101):
            nombre = f'Receta {i}'
            rec, _ = Receta.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': f'Receta de {nombre}'}
            )
            rec.tipos_receta.set([tipo_receta_objs[k] for k in tipos_default])
            rec.momentos_dia.set([tipo_objs[k] for k in momentos_default])
            rec_objs[nombre] = rec

        # 3b. Recetas catálogo: 50 bebidas, postres y frutas (solo bajo demanda con este comando)
        _cargar_recetas_bebidas_postres_frutas(Receta, TipoReceta, tipo_receta_objs)

        # 4. RecetaIngrediente (algunas recetas con ingredientes; unidad = UnidadMedida por símbolo)
        def add_ri(receta_nombre, ingrediente_nombre, cantidad, unidad_simbolo):
            r, i = rec_objs[receta_nombre], ing_objs[ingrediente_nombre]
            um = um_objs.get(unidad_simbolo) or um_objs['un']
            RecetaIngrediente.objects.get_or_create(
                receta=r, ingrediente=i,
                defaults={'cantidad': Decimal(str(cantidad)), 'unidad_medida': um}
            )
        add_ri('Ensalada mixta', 'Lechuga', 0.2, 'kg')
        add_ri('Ensalada mixta', 'Tomate', 0.1, 'kg')
        add_ri('Ensalada mixta', 'Cebolla', 0.05, 'kg')
        add_ri('Pechuga a la plancha', 'Pollo', 0.2, 'kg')
        add_ri('Pechuga a la plancha', 'Aceite', 0.01, 'lt')
        add_ri('Arroz con verduras', 'Arroz', 0.1, 'kg')
        add_ri('Arroz con verduras', 'Zanahoria', 0.05, 'kg')
        add_ri('Arroz con verduras', 'Cebolla', 0.03, 'kg')
        add_ri('Tortilla de huevos', 'Huevo', 2, 'un')
        add_ri('Tortilla de huevos', 'Aceite', 0.01, 'lt')
        add_ri('Fruta fresca', 'Manzana', 0.15, 'kg')
        add_ri('Fruta fresca', 'Plátano', 0.1, 'kg')
        add_ri('Batido de plátano', 'Plátano', 0.15, 'kg')
        add_ri('Batido de plátano', 'Leche', 0.2, 'lt')
        add_ri('Sándwich integral', 'Pan', 1, 'un')
        add_ri('Sándwich integral', 'Queso', 0.03, 'kg')
        # Recetas 16-100: asignar 2 ingredientes distintos por receta
        ing_nombres = list(ing_objs.keys())
        for i in range(16, 101):
            rec_nom = f'Receta {i}'
            idx_a = (i * 3) % len(ing_nombres)
            idx_b = (i * 7 + 11) % len(ing_nombres)
            if idx_a == idx_b:
                idx_b = (idx_b + 1) % len(ing_nombres)
            for idx in (idx_a, idx_b):
                ing_nom = ing_nombres[idx]
                um = ing_objs[ing_nom].unidad_medida
                RecetaIngrediente.objects.get_or_create(
                    receta=rec_objs[rec_nom], ingrediente=ing_objs[ing_nom],
                    defaults={'cantidad': Decimal('0.1'), 'unidad_medida': um}
                )

        # 5. Planes
        planes_data = [
            ('Básico', Decimal('150.00'), 'Plan estándar'),
            ('Proteico', Decimal('180.00'), 'Alto en proteínas'),
            ('Light', Decimal('170.00'), 'Bajo en calorías'),
        ]
        plan_objs = {}
        for nombre, precio, desc in planes_data:
            p, _ = Plan.objects.get_or_create(nombre=nombre, defaults={'precio_base': precio, 'descripcion': desc})
            plan_objs[nombre] = p

        # 6. Clientes: 500 total (400 activos, 100 inactivos)
        cli_objs = {}
        for i in range(1, 501):
            nombre = f'Cliente {i:03d}'
            email = f'cliente{i:03d}@ejemplo.com'
            tel = f'600{i:06d}'
            activo = i <= 400
            c, _ = Cliente.objects.get_or_create(
                email=email,
                defaults={'nombre': nombre, 'telefono': tel, 'activo': activo}
            )
            cli_objs[nombre] = c

        # 7. IngredienteNoGustado (algunos clientes no gustan de algo)
        IngredienteNoGustado.objects.get_or_create(
            cliente=cli_objs['Cliente 001'], ingrediente=ing_objs['Pimiento'],
            defaults={}
        )
        IngredienteNoGustado.objects.get_or_create(
            cliente=cli_objs['Cliente 002'], ingrediente=ing_objs['Ajo'],
            defaults={}
        )

        # 8. Contratos (primeros 5 clientes activos con plan)
        contratos_data = [
            ('Cliente 001', 'Básico', hoy - timedelta(days=30), None, Decimal('150.00'), 'mensual'),
            ('Cliente 002', 'Proteico', hoy - timedelta(days=15), hoy + timedelta(days=75), Decimal('180.00'), 'mensual'),
            ('Cliente 003', 'Básico', hoy - timedelta(days=7), None, Decimal('150.00'), 'mensual'),
            ('Cliente 004', 'Light', hoy, hoy + timedelta(days=90), Decimal('170.00'), 'mensual'),
            ('Cliente 005', 'Proteico', hoy - timedelta(days=60), hoy + timedelta(days=30), Decimal('180.00'), 'mensual'),
        ]
        cont_objs = []
        for cli_nom, plan_nom, f_inicio, f_fin, precio, freq in contratos_data:
            c, _ = Contrato.objects.get_or_create(
                cliente=cli_objs[cli_nom],
                plan=plan_objs[plan_nom],
                defaults={
                    'fecha_inicio': f_inicio, 'fecha_fin': f_fin, 'precio': precio, 'frecuencia_pago': freq,
                    'direccion_entrega': 'Calle Ejemplo 123, Ciudad', 'dias_entrega': ['lunes', 'martes', 'miercoles', 'jueves', 'viernes'],
                    'estado': 'activo',
                }
            )
            cont_objs.append(c)

        # 9. Dietas (opcional, no usadas por defecto pero existen)
        dieta_std, _ = Dieta.objects.get_or_create(nombre='Estándar', defaults={'activa': True})
        dieta_std.planes.set([plan_objs['Básico'], plan_objs['Light']])
        dieta_prot, _ = Dieta.objects.get_or_create(nombre='Alta proteína', defaults={'activa': True})
        dieta_prot.planes.set([plan_objs['Proteico']])
        # DietaReceta (algunas)
        for dr_nombre, tc_nombre, rec_nombre, orden in [
            ('Estándar', 'Desayuno', 'Tortilla de huevos', 1),
            ('Estándar', 'Desayuno', 'Pan con aceite', 2),
            ('Estándar', 'Comida', 'Ensalada mixta', 1),
            ('Estándar', 'Comida', 'Pechuga a la plancha', 2),
            ('Alta proteína', 'Comida', 'Pechuga a la plancha', 1),
            ('Alta proteína', 'Comida', 'Arroz con verduras', 2),
        ]:
            DietaReceta.objects.get_or_create(
                dieta=dieta_std if dr_nombre == 'Estándar' else dieta_prot,
                tipo_comida=tipo_objs[tc_nombre],
                receta=rec_objs[rec_nombre],
                defaults={'orden': orden}
            )

        # 10. Entregadores
        ent1, _ = Entregador.objects.get_or_create(
            nombre='Pedro Repartidor', defaults={'telefono': '611222333', 'vehiculo': 'Furgoneta'}
        )
        ent2, _ = Entregador.objects.get_or_create(
            nombre='Sara Entregas', defaults={'telefono': '622333444', 'vehiculo': 'Moto'}
        )

        # 11. Rutas y RutaCliente
        ruta, _ = Ruta.objects.get_or_create(
            fecha=hoy, entregador=ent1, defaults={'activa': True}
        )
        for i, contrato in enumerate(cont_objs[:3], 1):
            RutaCliente.objects.get_or_create(
                ruta=ruta, contrato=contrato,
                defaults={'orden_entrega': i, 'direccion_entrega': {}}
            )

        # 12. PlanificacionMenu y PlanificacionMenuReceta
        for plan_nom in ['Básico', 'Proteico', 'Light']:
            pm, _ = PlanificacionMenu.objects.get_or_create(
                fecha=hoy, plan=plan_objs[plan_nom], defaults={}
            )
            for tc_nom, rec_nom, orden in [
                ('Desayuno', 'Tortilla de huevos', 1),
                ('Media mañana', 'Fruta fresca', 1),
                ('Comida', 'Ensalada mixta', 1),
                ('Comida', 'Pechuga a la plancha', 2),
                ('Merienda', 'Yogur con frutas', 1),
                ('Cena', 'Sándwich integral', 1),
            ]:
                PlanificacionMenuReceta.objects.get_or_create(
                    planificacion_menu=pm,
                    tipo_comida=tipo_objs[tc_nom],
                    receta=rec_objs[rec_nom],
                    defaults={'orden': orden}
                )

        # 13. PlanificacionClienteSustituta (Cliente 001 no gusta pimiento; sustituir Ensalada mixta por Crema de zanahoria)
        contrato_1 = cont_objs[0]  # Cliente 001 - Básico
        PlanificacionClienteSustituta.objects.get_or_create(
            fecha=hoy, contrato=contrato_1, tipo_comida=tipo_objs['Comida'], receta_original=rec_objs['Ensalada mixta'],
            defaults={'receta_sustituta': rec_objs['Crema de zanahoria']}
        )

        # 14. DetalleCocina
        DetalleCocina.objects.get_or_create(fecha=hoy, defaults={'notas': 'Notas de prueba para cocina'})

        # 15. Facturas y Pagos
        periodo_desde = hoy.replace(day=1)
        periodo_hasta = (periodo_desde + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        for contrato in cont_objs[:3]:
            fact, _ = Factura.objects.get_or_create(
                contrato=contrato,
                periodo_desde=periodo_desde,
                defaults={
                    'periodo_hasta': periodo_hasta,
                    'fecha_emision': hoy,
                    'fecha_vencimiento': hoy + timedelta(days=15),
                    'monto': contrato.precio,
                    'estado': 'pendiente',
                }
            )
            if contrato.cliente.nombre == 'Cliente 001':
                Pago.objects.get_or_create(
                    factura=fact,
                    fecha_pago=hoy,
                    defaults={'monto': Decimal('75.00'), 'metodo_pago': 'transferencia'}
                )

        # 16. PrevisionCompra
        prev, _ = PrevisionCompra.objects.get_or_create(
            fecha_desde=hoy,
            fecha_hasta=hoy + timedelta(days=7),
            defaults={'notas': 'Previsión de prueba'}
        )
        prev.calcular_items()
