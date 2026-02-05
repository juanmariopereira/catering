"""
Actualiza el campo nombre de los clientes existentes asignando nombres y apellidos
reales (españoles/latinoamericanos). No crea ni elimina clientes; solo modifica
el atributo nombre de los registros ya existentes.

Uso:
  python manage.py actualizar_nombres_clientes
  python manage.py actualizar_nombres_clientes --dry-run   # solo mostrar qué nombres se asignarían
  python manage.py actualizar_nombres_clientes --limite 100   # solo los primeros 100
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from clients.models import Cliente


# Nombres (pila) y apellidos reales para combinar
NOMBRES = [
    'María', 'José', 'Juan', 'Ana', 'Luis', 'Carmen', 'Francisco', 'Laura', 'Carlos', 'Isabel',
    'Miguel', 'Rosa', 'Antonio', 'Elena', 'Manuel', 'Marta', 'Pedro', 'Sara', 'Javier', 'Paula',
    'David', 'Lucía', 'Daniel', 'Claudia', 'Pablo', 'Andrea', 'Alejandro', 'Julia', 'Raúl', 'Sofía',
    'Fernando', 'Patricia', 'Jesús', 'Cristina', 'Alberto', 'Natalia', 'Roberto', 'Eva', 'Diego', 'Alba',
    'Andrés', 'Marina', 'Francisco', 'Lorena', 'Ángel', 'Raquel', 'Rubén', 'Silvia', 'Víctor', 'Inés',
]

APELLIDOS = [
    'García', 'Rodríguez', 'Martínez', 'López', 'González', 'Sánchez', 'Pérez', 'Romero', 'Fernández', 'Díaz',
    'Torres', 'Ramírez', 'Flores', 'Rivera', 'Gómez', 'Reyes', 'Morales', 'Herrera', 'Ortiz', 'Jiménez',
    'Ruiz', 'Mendoza', 'Vargas', 'Castro', 'Romero', 'Silva', 'Rojas', 'Espinoza', 'Medina', 'Guerrero',
    'Moreno', 'Muñoz', 'Salazar', 'Vega', 'Castillo', 'Sandoval', 'Contreras', 'Figueroa', 'Fuentes', 'Valdez',
]


class Command(BaseCommand):
    help = 'Asigna nombres y apellidos reales a los clientes existentes (solo actualiza el campo nombre).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué nombres se asignarían, sin guardar.',
        )
        parser.add_argument(
            '--limite',
            type=int,
            default=None,
            help='Máximo número de clientes a actualizar (por defecto todos).',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla para aleatoriedad reproducible (default: 42).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limite = options['limite']
        seed = options['seed']

        clientes = Cliente.objects.order_by('id')
        if limite is not None:
            clientes = clientes[:limite]
        clientes = list(clientes)

        if not clientes:
            self.stdout.write(self.style.WARNING('No hay clientes para actualizar.'))
            return

        random.seed(seed)
        # Combinaciones nombre + apellido (50*40 = 2000 únicas)
        combinaciones = [
            f'{nombre} {apellido}'
            for nombre in NOMBRES
            for apellido in APELLIDOS
        ]
        random.shuffle(combinaciones)
        # Si hay más clientes que combinaciones, añadir más con doble apellido
        while len(combinaciones) < len(clientes):
            combinaciones.append(
                f'{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}'
            )

        if dry_run:
            self.stdout.write(f'Se asignarían nombres a {len(clientes)} cliente(s) (sin guardar):')
            for i, cliente in enumerate(clientes[:15]):
                self.stdout.write(f'  {cliente.id}: "{cliente.nombre}" -> "{combinaciones[i]}"')
            if len(clientes) > 15:
                self.stdout.write(f'  ... y {len(clientes) - 15} más.')
            self.stdout.write(self.style.WARNING('Ejecute sin --dry-run para guardar los cambios.'))
            return

        with transaction.atomic():
            actualizados = 0
            for i, cliente in enumerate(clientes):
                nuevo_nombre = combinaciones[i]
                if cliente.nombre != nuevo_nombre:
                    cliente.nombre = nuevo_nombre
                    cliente.save(update_fields=['nombre'])
                    actualizados += 1

        self.stdout.write(self.style.SUCCESS(f'Actualizados {actualizados} de {len(clientes)} cliente(s).'))
