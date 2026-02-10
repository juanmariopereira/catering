"""
Tests for stop state machine: valid transitions, invalid transitions (409).
"""
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
from deliveries.services.event_processor import process_event, EventProcessingError

User = get_user_model()


class StopStateMachineTests(TestCase):
    """Test state transitions enforced server-side."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='courier1', password='testpass123', is_staff=False
        )
        self.entregador = Entregador.objects.create(
            nombre='Courier One',
            telefono='+123',
            user=self.user,
            activo=True,
        )
        self.profile = CourierProfile.objects.create(
            user=self.user,
            entregador=self.entregador,
        )
        self.cliente = Cliente.objects.create(nombre='Cliente Test', telefono='+1')
        self.plan = Plan.objects.create(nombre='Plan Test', precio_base=100)
        self.contrato = Contrato.objects.create(
            cliente=self.cliente,
            plan=self.plan,
            fecha_inicio='2025-01-01',
            precio=100,
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
            state=StopState.PENDING,
        )

    def test_pending_to_en_route_via_location_ping(self):
        """First LOCATION_PING should set first stop to EN_ROUTE."""
        import uuid
        rid = uuid.uuid4()
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.LOCATION_PING,
            payload={'latitude': 19.0, 'longitude': -99.0},
        )
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.EN_ROUTE)

    def test_en_route_to_arrived_valid(self):
        """EN_ROUTE -> ARRIVED with ATTEMPT_ARRIVE is valid (courier at stop)."""
        self.stop.state = StopState.EN_ROUTE
        self.stop.save()
        rid = __import__('uuid').uuid4()
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.stop.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.ARRIVED)

    def test_arrived_to_delivered_valid(self):
        """ARRIVED -> DELIVERED with ATTEMPT_DELIVER is valid."""
        self.stop.state = StopState.ARRIVED
        self.stop.save()
        rid = __import__('uuid').uuid4()
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.ATTEMPT_DELIVER,
            stop_id=self.stop.pk,
            payload={},
        )
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.DELIVERED)

    def test_arrived_to_failed_valid(self):
        """ARRIVED -> FAILED with ATTEMPT_FAIL is valid."""
        self.stop.state = StopState.ARRIVED
        self.stop.save()
        rid = __import__('uuid').uuid4()
        process_event(
            self.user,
            request_id=rid,
            action_type=ActionType.ATTEMPT_FAIL,
            stop_id=self.stop.pk,
            payload={'reason': 'Customer not home'},
        )
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.FAILED)

    def test_invalid_transition_returns_409(self):
        """PENDING -> DELIVERED directly is invalid (409)."""
        rid = __import__('uuid').uuid4()
        with self.assertRaises(EventProcessingError) as ctx:
            process_event(
                self.user,
                request_id=rid,
                action_type=ActionType.ATTEMPT_DELIVER,
                stop_id=self.stop.pk,
                payload={},
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_delivered_no_further_transitions(self):
        """DELIVERED stop cannot transition."""
        self.stop.state = StopState.DELIVERED
        self.stop.save()
        rid = __import__('uuid').uuid4()
        with self.assertRaises(EventProcessingError) as ctx:
            process_event(
                self.user,
                request_id=rid,
                action_type=ActionType.ATTEMPT_ARRIVE,
                stop_id=self.stop.pk,
                payload={},
            )
        self.assertEqual(ctx.exception.status_code, 409)
