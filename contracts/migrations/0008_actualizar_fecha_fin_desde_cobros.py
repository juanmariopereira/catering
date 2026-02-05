# Migración de datos: actualizar fecha_fin de cada contrato al fin del período del último cobro

from django.db import migrations
from django.db.models import Max


def actualizar_fecha_fin_desde_cobros(apps, schema_editor):
    """Para cada contrato, pone fecha_fin = max(periodo_hasta de sus cobros) si aplica."""
    Contrato = apps.get_model('contracts', 'Contrato')
    Cobro = apps.get_model('billing', 'Cobro')
    for contrato in Contrato.objects.all():
        ultimo = Cobro.objects.filter(contrato_id=contrato.pk).aggregate(
            max_hasta=Max('periodo_hasta')
        )['max_hasta']
        if ultimo is not None:
            if contrato.fecha_fin is None or ultimo > contrato.fecha_fin:
                contrato.fecha_fin = ultimo
                contrato.save(update_fields=['fecha_fin'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0007_estado_calculado'),
        ('billing', '0002_factura_a_cobro'),  # asegurar que Cobro existe
    ]

    operations = [
        migrations.RunPython(actualizar_fecha_fin_desde_cobros, noop),
    ]
