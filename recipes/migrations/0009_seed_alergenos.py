# Data migration: alérgenos predefinidos

from django.db import migrations


def seed_alergenos(apps, schema_editor):
    Alergeno = apps.get_model('recipes', 'Alergeno')
    datos = [
        (1, 'Gluten'),
        (2, 'Lactosa'),
        (3, 'Frutos secos'),
        (4, 'Mariscos'),
        (5, 'Huevo'),
        (6, 'Soja'),
        (7, 'Apio'),
        (8, 'Mostaza'),
        (9, 'Sésamo'),
        (10, 'Sulfitos'),
        (11, 'Cacahuete'),
        (12, 'Pescado'),
    ]
    for orden, nombre in datos:
        Alergeno.objects.get_or_create(nombre=nombre, defaults={'orden': orden, 'activo': True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0008_add_alergeno_model'),
    ]

    operations = [
        migrations.RunPython(seed_alergenos, noop),
    ]
