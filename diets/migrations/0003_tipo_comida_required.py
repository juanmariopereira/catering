# Generated manually

from django.db import migrations, models
import django.db.models.deletion


def asegurar_tipo_comida(apps, schema_editor):
    """Asigna 'Comida' a cualquier DietaReceta que aún tenga tipo_comida null."""
    TipoComida = apps.get_model('diets', 'TipoComida')
    DietaReceta = apps.get_model('diets', 'DietaReceta')
    comida = TipoComida.objects.filter(nombre='Comida').first()
    if comida:
        DietaReceta.objects.filter(tipo_comida__isnull=True).update(tipo_comida=comida)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('diets', '0002_add_tipo_comida'),
    ]

    operations = [
        migrations.RunPython(asegurar_tipo_comida, noop),
        migrations.AlterField(
            model_name='dietareceta',
            name='tipo_comida',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='dieta_recetas',
                to='diets.tipocomida',
                verbose_name='Momento / Tipo de comida',
            ),
        ),
    ]
