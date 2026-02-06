# Generated manually

from django.db import migrations, models
import django.db.models.deletion


def noop(apps, schema_editor):
    """Sin datos ficticios: no se asigna tipo_comida por defecto."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('diets', '0002_add_tipo_comida'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
        migrations.AlterField(
            model_name='dietareceta',
            name='tipo_comida',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='dieta_recetas',
                to='diets.tipocomida',
                verbose_name='Momento / Tipo de comida',
            ),
        ),
    ]
