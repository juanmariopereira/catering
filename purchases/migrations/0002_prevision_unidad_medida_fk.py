# Multi-step migration: CharField unidad_medida -> FK(UnidadMedida)

import django.db.models.deletion
from django.db import migrations, models


def migrar_unidad_medida_prevision(apps, schema_editor):
    """Asigna FK UnidadMedida en PrevisionCompraItem desde el string existente."""
    UnidadMedida = apps.get_model('recipes', 'UnidadMedida')
    PrevisionCompraItem = apps.get_model('purchases', 'PrevisionCompraItem')
    for item in PrevisionCompraItem.objects.all():
        if item.unidad_medida_old:
            um, _ = UnidadMedida.objects.get_or_create(
                nombre=item.unidad_medida_old,
                defaults={'orden': 99}
            )
        else:
            um = UnidadMedida.objects.filter(nombre='Unidad').first()
            if not um:
                um = UnidadMedida.objects.create(nombre='Unidad', orden=4)
        item.unidad_medida_id = um.id
        item.save(update_fields=['unidad_medida_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0001_initial'),
        ('recipes', '0003_unidad_medida_parametrizable'),
    ]

    operations = [
        migrations.RenameField(
            model_name='previsioncompraitem',
            old_name='unidad_medida',
            new_name='unidad_medida_old',
        ),
        migrations.AddField(
            model_name='previsioncompraitem',
            name='unidad_medida',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='prevision_items',
                to='recipes.unidadmedida',
                verbose_name='Unidad de medida',
            ),
        ),
        migrations.RunPython(migrar_unidad_medida_prevision, noop),
        migrations.RemoveField(
            model_name='previsioncompraitem',
            name='unidad_medida_old',
        ),
        migrations.AlterField(
            model_name='previsioncompraitem',
            name='unidad_medida',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='prevision_items',
                to='recipes.unidadmedida',
                verbose_name='Unidad de medida',
            ),
        ),
    ]
