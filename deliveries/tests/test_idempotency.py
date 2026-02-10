"""
Tests for idempotency: repeated request_id returns 200 and does not corrupt state.
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from routes.models import Entregador, Ruta, RutaCliente
from contracts.models import Contrato
from clients.models import Cliente
from plans.models import Plan

from deliveries.models import (
    CourierProfile,
    DeliveryRoute,
    DeliveryStop,
    StopState,
    ActionType,
    DeliveryActionEvent,
)
from deliveries.services.event_processor import process_event

User = get_user_model()


class IdempotencyTests(TestCase):
    """Duplicate event submission must not corrupt state."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='courier2', password='testpass123', is_staff=False
        )
        self.entregador = Entregador.objects.create(
            nombre='Courier Two',
            telefono='+456',
            user=self.user,
            activo=True,
        )
        CourierProfile.objects.create(user=self.user, entregador=self.entregador)
        self.cliente = Cliente.objects.create(nombre='Cliente 2', telefono='+2')
        self.plan = Plan.objects.create(nombre='Plan 2', precio_base=200)
        self.contrato = Contrato.objects.create(
            cliente=self.cliente,
            plan=self.plan,
            fecha_inicio='2025-01-01',
            precio=200,
            latitud='19.432608',
            longitud='-99.133209',
        )
        self.ruta = Ruta.objects.create(
            fecha=timezone.localdate(),
            entregador=self.entregador,
            activa=True,
        )
        self.ruta_cliente = RutaCliente.objects.create(
            ruta=self.ruta,
            contrato=self.contrato,
            orden_entrega=1,
        )
        self.delivery_route = DeliveryRoute.objects.create(ruta=self.ruta)
        self.stop = DeliveryStop.objects.create(
            delivery_route=self.delivery_route,
            ruta_cliente=self.ruta_cliente,
            sequence=1,
            state=StopState.EN_ROUTE,
        )

    def test_duplicate_request_id_returns_same_context(self):
        """Same request_id twice: second call returns 200 with current context, no duplicate event."""
        rid = uuid.uuid4()
        _, ctx1 = process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.stop.pk,
            payload={},
        )
        count_before = DeliveryActionEvent.objects.filter(request_id=rid).count()
        self.assertEqual(count_before, 1)
        _, ctx2 = process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.stop.pk,
            payload={},
        )
        count_after = DeliveryActionEvent.objects.filter(request_id=rid).count()
        self.assertEqual(count_after, 1)
        self.assertEqual(ctx1['current_active_stop_id'], ctx2['current_active_stop_id'])
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.ARRIVED)

    def test_duplicate_location_ping_idempotent(self):
        """Duplicate LOCATION_PING with same request_id only creates one event."""
        rid = uuid.uuid4()
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.LOCATION_PING,
            payload={'latitude': 19.0, 'longitude': -99.0},
        )
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.LOCATION_PING,
            payload={'latitude': 19.1, 'longitude': -99.1},
        )
        self.assertEqual(DeliveryActionEvent.objects.filter(request_id=rid).count(), 1)
