# Generated manually for direccion + link_maps (replacing direcciones JSON)

from django.db import migrations, models


def migrar_direcciones_a_texto(apps, schema_editor):
    """Copia el primer valor de direcciones (si existe) a direccion."""
    Cliente = apps.get_model('clients', 'Cliente')
    for c in Cliente.objects.all():
        d = c.direcciones
        texto = ''
        if d and isinstance(d, list) and len(d) > 0:
            prim = d[0]
            if isinstance(prim, str):
                texto = prim
            elif isinstance(prim, dict):
                texto = prim.get('texto') or prim.get('direccion') or prim.get('address') or ''
        Cliente.objects.filter(pk=c.pk).update(direccion=texto)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='direccion',
            field=models.TextField(blank=True, default='', help_text='Dirección literal del cliente', verbose_name='Dirección'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='link_maps',
            field=models.URLField(blank=True, help_text='URL de Google Maps con la ubicación (opcional)', max_length=500, null=True, verbose_name='Enlace Google Maps'),
        ),
        migrations.RunPython(migrar_direcciones_a_texto, noop),
        migrations.RemoveField(
            model_name='cliente',
            name='direcciones',
        ),
    ]
