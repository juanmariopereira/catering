# Sin datos ficticios: los alérgenos se crean desde la app o datos reales.

from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0008_add_alergeno_model'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
