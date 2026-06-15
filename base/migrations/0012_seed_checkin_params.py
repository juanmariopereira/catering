from django.db import migrations


PARAMS = [
    ('checkin_auto', 'false',
     'Check-in automático por GPS para repartidores (true/false). Marca la llegada al entrar en el radio.'),
    ('checkin_radio_metros', '150',
     'Radio de aproximación en metros para considerar que el repartidor llegó a la parada.'),
    ('ping_intervalo_segundos', '5',
     'Cada cuántos segundos la app del repartidor envía su ubicación GPS.'),
]


def seed(apps, schema_editor):
    ParametroSistema = apps.get_model('base', 'ParametroSistema')
    for clave, valor, descripcion in PARAMS:
        ParametroSistema.objects.get_or_create(
            clave=clave,
            defaults={'valor': valor, 'descripcion': descripcion},
        )


def unseed(apps, schema_editor):
    ParametroSistema = apps.get_model('base', 'ParametroSistema')
    ParametroSistema.objects.filter(clave__in=[c for c, _, _ in PARAMS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0011_asignacion_fallback'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
