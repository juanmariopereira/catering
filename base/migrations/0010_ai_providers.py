import os

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# Modelos por defecto por proveedor: (modelo_id, nombre visible).
# Solo OpenAI se habilita por defecto (con la clave de entorno) y se asigna a
# todos los usos, para preservar el comportamiento actual. El resto quedan
# creados pero deshabilitados hasta que se configure su clave en el admin.
MODELOS_DEFECTO = {
    'openai': [
        ('gpt-4o-mini', 'OpenAI · GPT-4o mini'),
        ('gpt-4o', 'OpenAI · GPT-4o'),
    ],
    'anthropic': [
        ('claude-opus-4-8', 'Claude Opus 4.8'),
        ('claude-sonnet-4-6', 'Claude Sonnet 4.6'),
        ('claude-haiku-4-5', 'Claude Haiku 4.5'),
    ],
    'gemini': [
        ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
    ],
    'grok': [
        ('grok-2-latest', 'Grok 2'),
        ('grok-beta', 'Grok Beta'),
    ],
}

NOMBRES_PROVEEDOR = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic (Claude)',
    'gemini': 'Google Gemini',
    'grok': 'xAI Grok',
}

# Las 8 acciones de IA del sistema (deben coincidir con AIRequestLog.ACCION_CHOICES).
ACCIONES = [
    'estimar_nutricion_ingrediente',
    'estimar_nutricion_receta',
    'sugerir_descripcion_receta',
    'sugerir_ingredientes_receta',
    'sugerir_dieta',
    'sugerir_menu',
    'importar_receta',
    'generar_mensaje_cliente',
]


def seed(apps, schema_editor):
    ProveedorIA = apps.get_model('base', 'ProveedorIA')
    ModeloIA = apps.get_model('base', 'ModeloIA')
    AsignacionUsoIA = apps.get_model('base', 'AsignacionUsoIA')

    openai_key = os.environ.get('OPENAI_API_KEY', '') or ''

    proveedores = {}
    for codigo in ('openai', 'anthropic', 'gemini', 'grok'):
        es_openai = codigo == 'openai'
        prov, _ = ProveedorIA.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': NOMBRES_PROVEEDOR[codigo],
                'api_key': openai_key if es_openai else '',
                'activo': bool(es_openai and openai_key.strip()),
            },
        )
        proveedores[codigo] = prov

    modelos = {}
    for codigo, lista in MODELOS_DEFECTO.items():
        prov = proveedores[codigo]
        for modelo_id, nombre in lista:
            modelo, _ = ModeloIA.objects.get_or_create(
                proveedor=prov,
                modelo_id=modelo_id,
                defaults={'nombre': nombre},
            )
            modelos[(codigo, modelo_id)] = modelo

    # Asignar todos los usos al modelo por defecto de OpenAI (gpt-4o-mini),
    # que es el que el sistema ya usaba.
    modelo_defecto = modelos.get(('openai', 'gpt-4o-mini'))
    for accion in ACCIONES:
        AsignacionUsoIA.objects.get_or_create(
            accion=accion,
            defaults={'modelo': modelo_defecto, 'activo': True},
        )


def unseed(apps, schema_editor):
    apps.get_model('base', 'AsignacionUsoIA').objects.all().delete()
    apps.get_model('base', 'ModeloIA').objects.all().delete()
    apps.get_model('base', 'ProveedorIA').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0009_create_profile_groups'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProveedorIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(choices=[('openai', 'OpenAI'), ('anthropic', 'Anthropic (Claude)'), ('gemini', 'Google Gemini'), ('grok', 'xAI Grok')], help_text='Proveedor de IA. Determina el SDK y el endpoint usados.', max_length=20, unique=True, verbose_name='Proveedor')),
                ('nombre', models.CharField(blank=True, max_length=100, verbose_name='Nombre visible')),
                ('api_key', models.CharField(blank=True, default='', help_text='Clave de API del proveedor. Si está vacía, el proveedor no se puede usar.', max_length=255, verbose_name='Clave API')),
                ('activo', models.BooleanField(default=False, help_text='Si está deshabilitado, ninguno de sus modelos se podrá usar.', verbose_name='Habilitado')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, verbose_name='Actualizado')),
            ],
            options={
                'verbose_name': 'Proveedor de IA',
                'verbose_name_plural': 'Proveedores de IA',
                'ordering': ['codigo'],
            },
        ),
        migrations.CreateModel(
            name='ModeloIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modelo_id', models.CharField(help_text='Identificador exacto del modelo en el proveedor (ej. gpt-4o-mini, claude-opus-4-8).', max_length=100, verbose_name='ID del modelo')),
                ('nombre', models.CharField(blank=True, max_length=120, verbose_name='Nombre visible')),
                ('activo', models.BooleanField(default=True, verbose_name='Habilitado')),
                ('tokens_por_minuto', models.PositiveIntegerField(default=100000, verbose_name='Tokens por minuto')),
                ('tokens_por_dia', models.PositiveIntegerField(default=2000000, verbose_name='Tokens por día')),
                ('requests_por_minuto', models.PositiveIntegerField(default=60, verbose_name='Solicitudes por minuto')),
                ('requests_por_dia', models.PositiveIntegerField(default=5000, verbose_name='Solicitudes por día')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, verbose_name='Actualizado')),
                ('proveedor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modelos', to='base.proveedoria', verbose_name='Proveedor')),
            ],
            options={
                'verbose_name': 'Modelo de IA',
                'verbose_name_plural': 'Modelos de IA',
                'ordering': ['proveedor__codigo', 'modelo_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='modeloia',
            constraint=models.UniqueConstraint(fields=('proveedor', 'modelo_id'), name='uniq_proveedor_modelo'),
        ),
        migrations.CreateModel(
            name='AsignacionUsoIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(choices=[('estimar_nutricion_ingrediente', 'Estimar nutrición ingrediente'), ('estimar_nutricion_receta', 'Estimar nutrición receta'), ('sugerir_descripcion_receta', 'Sugerir descripción receta'), ('sugerir_ingredientes_receta', 'Sugerir ingredientes receta'), ('sugerir_dieta', 'Sugerir dieta personalizada'), ('sugerir_menu', 'Sugerir menú'), ('importar_receta', 'Importar receta desde texto'), ('generar_mensaje_cliente', 'Generar mensaje personalizado cliente')], max_length=50, unique=True, verbose_name='Uso de IA')),
                ('activo', models.BooleanField(default=True, help_text='Si está deshabilitado, este uso de IA queda desactivado.', verbose_name='Habilitado')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, verbose_name='Actualizado')),
                ('modelo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asignaciones', to='base.modeloia', verbose_name='Modelo asignado')),
            ],
            options={
                'verbose_name': 'Asignación de uso de IA',
                'verbose_name_plural': 'Asignaciones de uso de IA',
                'ordering': ['accion'],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
