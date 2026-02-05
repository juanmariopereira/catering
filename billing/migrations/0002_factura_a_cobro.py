# Generated manually: reemplazo Factura por Cobro

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel('Factura', 'Cobro'),
        migrations.RenameField(model_name='cobro', old_name='numero_factura', new_name='numero_cobro'),
        migrations.RenameField(model_name='cobro', old_name='fecha_emision', new_name='fecha_generacion'),
        migrations.AlterField(
            model_name='cobro',
            name='fecha_vencimiento',
            field=models.DateField(
                blank=True,
                help_text='Se calcula automáticamente si se deja vacío (según período y frecuencia del contrato).',
                null=True,
                verbose_name='Fecha de vencimiento',
            ),
        ),
        migrations.RenameField(model_name='pago', old_name='factura', new_name='cobro'),
        migrations.AlterField(
            model_name='cobro',
            name='fecha_generacion',
            field=models.DateField(
                blank=True,
                help_text='Fecha en que se generó el cobro (opcional).',
                null=True,
                verbose_name='Fecha de generación',
            ),
        ),
        migrations.AlterModelOptions(
            name='cobro',
            options={
                'ordering': ['-periodo_hasta', '-numero_cobro'],
                'verbose_name': 'Cobro',
                'verbose_name_plural': 'Cobros',
            },
        ),
    ]
