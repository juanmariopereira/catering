# Data migration: fill PlantillaRuta, PlantillaRutaCliente, EntregaDia from Ruta/RutaCliente

import uuid
from django.db import migrations, models


def _get_or_create_plantilla(apps, entregador):
    PlantillaRuta = apps.get_model('routes', 'PlantillaRuta')
    pl, _ = PlantillaRuta.objects.get_or_create(
        entregador=entregador,
        defaults={'activa': True},
    )
    return pl


def migrate_plantilla_and_entrega_dia(apps, schema_editor):
    Ruta = apps.get_model('routes', 'Ruta')
    RutaCliente = apps.get_model('routes', 'RutaCliente')
    PlantillaRuta = apps.get_model('routes', 'PlantillaRuta')
    PlantillaRutaCliente = apps.get_model('routes', 'PlantillaRutaCliente')
    EntregaDia = apps.get_model('routes', 'EntregaDia')
    Entregador = apps.get_model('routes', 'Entregador')

    # 1) Create PlantillaRuta for each entregador that has at least one Ruta
    entregador_ids = set(
        Ruta.objects.values_list('entregador_id', flat=True).distinct()
    )
    for eid in entregador_ids:
        entregador = Entregador.objects.get(pk=eid)
        _get_or_create_plantilla(apps, entregador)

    # 2) Fix any existing PlantillaRutaCliente with blank codigo (from a previous failed run)
    used_codigos = set(
        PlantillaRutaCliente.objects.exclude(codigo_entrega='').exclude(codigo_entrega__isnull=True)
        .values_list('codigo_entrega', flat=True)
    )
    for prc in PlantillaRutaCliente.objects.filter(models.Q(codigo_entrega='') | models.Q(codigo_entrega__isnull=True)):
        while True:
            codigo = uuid.uuid4().hex[:8].upper()
            if codigo not in used_codigos:
                break
        used_codigos.add(codigo)
        prc.codigo_entrega = codigo
        prc.save(update_fields=['codigo_entrega'])

    # 3) For each (entregador, contrato) from RutaCliente, add PlantillaRutaCliente
    #    Use orden_entrega from the RutaCliente with the latest ruta.fecha
    seen = set()  # (entregador_id, contrato_id)
    for rc in RutaCliente.objects.select_related('ruta', 'contrato').order_by('-ruta__fecha'):
        key = (rc.ruta.entregador_id, rc.contrato_id)
        if key in seen:
            continue
        seen.add(key)
        plantilla = PlantillaRuta.objects.get(entregador_id=rc.ruta.entregador_id)
        codigo = rc.codigo_entrega.strip() if rc.codigo_entrega else ''
        while not codigo or codigo in used_codigos:
            codigo = uuid.uuid4().hex[:8].upper()
        used_codigos.add(codigo)
        PlantillaRutaCliente.objects.get_or_create(
            plantilla_ruta=plantilla,
            contrato_id=rc.contrato_id,
            defaults={'orden_entrega': rc.orden_entrega, 'codigo_entrega': codigo},
        )

    # 4) Create EntregaDia from RutaCliente that have state (entregada, no_entregada, etc.)
    for rc in RutaCliente.objects.select_related('ruta').all():
        if not rc.entregada and not rc.no_entregada:
            continue
        entregador_id = rc.ruta.entregador_id
        fecha = rc.ruta.fecha
        EntregaDia.objects.get_or_create(
            entregador_id=entregador_id,
            contrato_id=rc.contrato_id,
            fecha=fecha,
            defaults={
                'entregada': rc.entregada,
                'fecha_entrega': rc.fecha_entrega,
                'marcadopor_entregada_id': rc.marcadopor_entregada_id,
                'no_entregada': rc.no_entregada,
                'motivo_no_entrega': rc.motivo_no_entrega or '',
                'fecha_no_entrega': rc.fecha_no_entrega,
                'marcadopor_no_entrega_id': rc.marcadopor_no_entrega_id,
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0008_add_plantilla_entrega_dia'),
    ]

    operations = [
        migrations.RunPython(migrate_plantilla_and_entrega_dia, noop),
    ]
