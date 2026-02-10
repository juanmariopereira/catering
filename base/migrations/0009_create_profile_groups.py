# Generated for profile groups: Admin, Cocina, Entregador

from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ('Admin', 'Cocina', 'Entregador'):
        Group.objects.get_or_create(name=name)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_add_user_action_log'),
    ]

    operations = [
        migrations.RunPython(create_groups, noop),
    ]
