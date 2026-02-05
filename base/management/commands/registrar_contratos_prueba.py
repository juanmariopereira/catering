"""
Comando para registrar 100 contratos de prueba para 70 usuarios,
con cobros y pagos en meses pasados y el actual (algunos vencidos, otros al día).

Uso:
  python manage.py registrar_contratos_prueba
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def _last_day_of_month(d):
    """Último día del mes de la fecha d."""
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


def _first_day_of_month(d):
    return d.replace(day=1)


class Command(BaseCommand):
    help = 'Registra 100 contratos para 70 usuarios, con cobros y pagos (meses pasados y actual).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla para números aleatorios (reproducibilidad).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from clients.models import Cliente
        from plans.models import Plan
        from contracts.models import Contrato
        from billing.models import Cobro, Pago

        seed = options['seed']
        random.seed(seed)
        hoy = date.today()
        inicio_mes_actual = _first_day_of_month(hoy)

        # 1. Asegurar al menos 70 clientes
        clientes_existentes = list(Cliente.objects.all().order_by('id')[:70])
        clientes = []
        for i in range(70):
            if i < len(clientes_existentes):
                clientes.append(clientes_existentes[i])
            else:
                idx = len(clientes_existentes) + (i - len(clientes_existentes)) + 1
                c = Cliente.objects.create(
                    nombre=f'Usuario prueba {idx:03d}',
                    email=f'usuarioprueba{idx:03d}@ejemplo.com',
                    telefono=f'600{idx:06d}',
                    activo=True,
                )
                clientes.append(c)
        self.stdout.write(f'Clientes disponibles: {len(clientes)}')

        # 2. Planes (deben existir)
        planes = list(Plan.objects.filter(activo=True).order_by('nombre'))
        if not planes:
            planes = [
                Plan.objects.create(nombre='Básico', precio_base=Decimal('150.00'), activo=True),
                Plan.objects.create(nombre='Proteico', precio_base=Decimal('180.00'), activo=True),
                Plan.objects.create(nombre='Light', precio_base=Decimal('170.00'), activo=True),
            ]
        self.stdout.write(f'Planes: {len(planes)}')

        # 3. Crear 100 contratos (repartidos entre 70 clientes: algunos con 1, otros con 2)
        # Fecha inicio: entre 5 meses atrás y primer día del mes actual
        contratos_creados = []
        for i in range(100):
            cliente = clientes[i % 70]
            plan = random.choice(planes)
            # Inicio: 0–5 meses atrás (primer día de un mes)
            meses_atras = random.randint(0, 5)
            if meses_atras == 0:
                fecha_inicio = inicio_mes_actual
            else:
                year = hoy.year
                month = hoy.month - meses_atras
                while month <= 0:
                    month += 12
                    year -= 1
                fecha_inicio = date(year, month, 1)
            precio = plan.precio_base
            # Algunos contratos con fecha_fin en el pasado (vencido), otros sin fin o en futuro
            if random.random() < 0.15:
                # Contrato “vencido”: fecha_fin hace 1–2 meses
                m = random.randint(1, 2)
                y, mo = hoy.year, hoy.month - m
                while mo <= 0:
                    mo += 12
                    y -= 1
                fecha_fin = _last_day_of_month(date(y, mo, 1))
            elif random.random() < 0.25:
                # Contrato con fin en el futuro
                fecha_fin = hoy + timedelta(days=random.randint(60, 180))
            else:
                fecha_fin = None
            contrato = Contrato.objects.create(
                cliente=cliente,
                plan=plan,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                precio=precio,
                frecuencia_pago='mensual',
                direccion_entrega='Calle Prueba 123',
                dias_entrega=['lunes', 'martes', 'miercoles', 'jueves', 'viernes'],
            )
            contratos_creados.append(contrato)
        self.stdout.write(f'Contratos creados: {len(contratos_creados)}')

        # 4. Para cada contrato: varios cobros (meses desde fecha_inicio hasta mes actual + 1)
        metodos_pago = ['efectivo', 'transferencia', 'tarjeta']
        cobros_creados = 0
        pagos_creados = 0
        for contrato in contratos_creados:
            # Meses a facturar: desde el mes de fecha_inicio hasta mes actual (inclusive)
            inicio = _first_day_of_month(contrato.fecha_inicio)
            num_meses = (hoy.year - inicio.year) * 12 + (hoy.month - inicio.month) + 1
            num_meses = max(2, min(num_meses, 6))  # Entre 2 y 6 cobros por contrato
            for m in range(num_meses):
                year = inicio.year
                month = inicio.month + m
                while month > 12:
                    month -= 12
                    year += 1
                periodo_desde = date(year, month, 1)
                periodo_hasta = _last_day_of_month(periodo_desde)
                if periodo_desde < contrato.fecha_inicio:
                    continue
                if Cobro.objects.filter(contrato=contrato, periodo_desde=periodo_desde).exists():
                    continue
                cobro = Cobro.objects.create(
                    contrato=contrato,
                    periodo_desde=periodo_desde,
                    periodo_hasta=periodo_hasta,
                    monto=contrato.precio,
                )
                cobros_creados += 1
                r = random.random()
                if r < 0.45:
                    # Pagada: pago por el monto total
                    dias_despues = random.randint(1, 14) if periodo_hasta < hoy else random.randint(0, 5)
                    fecha_pago = min(periodo_hasta + timedelta(days=dias_despues), hoy)
                    Pago.objects.create(
                        cobro=cobro,
                        fecha_pago=fecha_pago,
                        monto=cobro.monto,
                        metodo_pago=random.choice(metodos_pago),
                    )
                    pagos_creados += 1
                elif r < 0.70 and cobro.fecha_vencimiento and cobro.fecha_vencimiento >= hoy:
                    # Pendiente al día: a veces con pago parcial
                    if random.random() < 0.3:
                        monto_parcial = round(cobro.monto * Decimal('0.5'), 2)
                        Pago.objects.create(
                            cobro=cobro,
                            fecha_pago=hoy - timedelta(days=random.randint(1, 5)),
                            monto=monto_parcial,
                            metodo_pago=random.choice(metodos_pago),
                        )
                        pagos_creados += 1
                # Resto: vencidos o pendientes sin pago (estado lo fija actualizar_estado)

        self.stdout.write(f'Cobros creados: {cobros_creados}')
        self.stdout.write(f'Pagos creados: {pagos_creados}')
        self.stdout.write(self.style.SUCCESS('Contratos, cobros y pagos de prueba registrados correctamente.'))
