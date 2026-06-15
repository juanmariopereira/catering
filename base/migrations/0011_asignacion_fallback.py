from django.db import migrations, models


ACCION_CHOICES = [
    ('estimar_nutricion_ingrediente', 'Estimar nutrición ingrediente'),
    ('estimar_nutricion_receta', 'Estimar nutrición receta'),
    ('sugerir_descripcion_receta', 'Sugerir descripción receta'),
    ('sugerir_ingredientes_receta', 'Sugerir ingredientes receta'),
    ('sugerir_dieta', 'Sugerir dieta personalizada'),
    ('sugerir_menu', 'Sugerir menú'),
    ('importar_receta', 'Importar receta desde texto'),
    ('generar_mensaje_cliente', 'Generar mensaje personalizado cliente'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0010_ai_providers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='asignacionusoia',
            options={
                'ordering': ['accion', 'orden'],
                'verbose_name': 'Asignación de uso de IA',
                'verbose_name_plural': 'Asignaciones de uso de IA',
            },
        ),
        migrations.AlterField(
            model_name='asignacionusoia',
            name='accion',
            field=models.CharField(choices=ACCION_CHOICES, db_index=True, max_length=50, verbose_name='Uso de IA'),
        ),
        migrations.AddField(
            model_name='asignacionusoia',
            name='orden',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Menor = mayor prioridad. Si este modelo falla o no está disponible, '
                          'se intenta el siguiente del mismo uso.',
                verbose_name='Orden (prioridad)',
            ),
        ),
        migrations.AddConstraint(
            model_name='asignacionusoia',
            constraint=models.UniqueConstraint(fields=('accion', 'modelo'), name='uniq_accion_modelo'),
        ),
    ]
