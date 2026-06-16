from django.db import migrations, models


# Modelos Groq por defecto: (modelo_id, nombre, TPM, TPD, RPM, RPD).
# Límites del plan gratuito de Groq (https://console.groq.com/docs/rate-limits);
# ajustables en el admin según el tier de la cuenta.
GROQ_MODELOS = [
    ('llama-3.3-70b-versatile', 'Groq · Llama 3.3 70B', 12000, 100000, 30, 1000),
    ('openai/gpt-oss-120b', 'Groq · GPT-OSS 120B', 8000, 200000, 30, 1000),
]

GROK_MODELOS = [
    ('grok-2-latest', 'Grok 2'),
    ('grok-beta', 'Grok Beta'),
]


def grok_a_groq(apps, schema_editor):
    """Renombra el proveedor 'grok' (xAI) a 'groq' y reemplaza sus modelos."""
    ProveedorIA = apps.get_model('base', 'ProveedorIA')
    ModeloIA = apps.get_model('base', 'ModeloIA')

    prov = ProveedorIA.objects.filter(codigo='grok').first()
    if prov:
        prov.codigo = 'groq'
        if (prov.nombre or '').strip() in ('', 'xAI Grok'):
            prov.nombre = 'Groq'
        prov.save(update_fields=['codigo', 'nombre'])
    else:
        prov = ProveedorIA.objects.filter(codigo='groq').first()
        if not prov:
            prov = ProveedorIA.objects.create(codigo='groq', nombre='Groq', api_key='', activo=False)

    # Quitar los modelos de Grok (xAI) y crear los de Groq.
    ModeloIA.objects.filter(
        proveedor=prov, modelo_id__in=[m[0] for m in GROK_MODELOS]
    ).delete()
    for modelo_id, nombre, tpm, tpd, rpm, rpd in GROQ_MODELOS:
        ModeloIA.objects.get_or_create(
            proveedor=prov,
            modelo_id=modelo_id,
            defaults={
                'nombre': nombre,
                'tokens_por_minuto': tpm,
                'tokens_por_dia': tpd,
                'requests_por_minuto': rpm,
                'requests_por_dia': rpd,
            },
        )


def groq_a_grok(apps, schema_editor):
    """Reversa: vuelve a 'grok' (xAI) con sus modelos."""
    ProveedorIA = apps.get_model('base', 'ProveedorIA')
    ModeloIA = apps.get_model('base', 'ModeloIA')

    prov = ProveedorIA.objects.filter(codigo='groq').first()
    if not prov:
        return
    prov.codigo = 'grok'
    if (prov.nombre or '').strip() in ('', 'Groq'):
        prov.nombre = 'xAI Grok'
    prov.save(update_fields=['codigo', 'nombre'])

    ModeloIA.objects.filter(
        proveedor=prov, modelo_id__in=[m[0] for m in GROQ_MODELOS]
    ).delete()
    for modelo_id, nombre in GROK_MODELOS:
        ModeloIA.objects.get_or_create(
            proveedor=prov, modelo_id=modelo_id, defaults={'nombre': nombre}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0012_seed_checkin_params'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proveedoria',
            name='codigo',
            field=models.CharField(
                choices=[
                    ('openai', 'OpenAI'),
                    ('anthropic', 'Anthropic (Claude)'),
                    ('gemini', 'Google Gemini'),
                    ('groq', 'Groq'),
                ],
                help_text='Proveedor de IA. Determina el SDK y el endpoint usados.',
                max_length=20,
                unique=True,
                verbose_name='Proveedor',
            ),
        ),
        migrations.RunPython(grok_a_groq, groq_a_grok),
    ]
