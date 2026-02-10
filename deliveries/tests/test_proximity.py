"""
Tests for proximity validation: backend decides if courier is near stop.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from routes.models import Entregador, Ruta, RutaCliente
from contracts.models import Contrato
from clients.models import Cliente
from plans.models import Plan

from deliveries.models import CourierProfile, DeliveryRoute, DeliveryStop, StopState
from deliveries.services.proximity import haversine_km, is_near_stop, get_stop_coordinates
from deliveries.services.event_processor import process_event, EventProcessingError
from deliveries.models import ActionType

User = get_user_model()


class ProximityTests(TestCase):
    """Backend computes distance (Haversine) and allows/denies ARRIVED/DELIVERED."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='courier3', password='testpass123', is_staff=False
        )
        self.entregador = Entregador.objects.create(
            nombre='Courier Three',
            telefono='+789',
            user=self.user,
            activo=True,
        )
        CourierProfile.objects.create(user=self.user, entregador=self.entregador)
        self.cliente = Cliente.objects.create(nombre='Cliente 3', telefono='+3')
        self.plan = Plan.objects.create(nombre='Plan 3', precio_base=300)
        self.contrato = Contrato.objects.create(
            cliente=self.cliente,
            plan=self.plan,
            fecha_inicio='2025-01-01',
            precio=300,
            latitud=Decimal('19.432608'),
            longitud=Decimal('-99.133209'),
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

    def test_haversine_same_point_zero(self):
        """Distance from point to itself is 0."""
        d = haversine_km(19.43, -99.13, 19.43, -99.13)
        self.assertAlmostEqual(d, 0.0, places=2)

    def test_haversine_known_distance(self):
        """Rough check: ~1 degree lat ~ 111 km."""
        d = haversine_km(19.0, -99.0, 20.0, -99.0)
        self.assertGreater(d, 100)
        self.assertLess(d, 120)

    def test_is_near_stop_when_close(self):
        """Courier at same coords as stop is near."""
        near, dist = is_near_stop(
            float(self.contrato.latitud),
            float(self.contrato.longitud),
            self.stop,
            threshold_km=0.2,
        )
        self.assertTrue(near)
        self.assertIsNotNone(dist)
        self.assertLess(dist, 0.01)

    def test_is_near_stop_when_far(self):
        """Courier far from stop is not near (default threshold 0.15 km)."""
        near, dist = is_near_stop(
            19.0,
            -99.0,
            self.stop,
            threshold_km=0.15,
        )
        self.assertFalse(near)
        self.assertIsNotNone(dist)

    def test_attempt_arrive_far_returns_409(self):
        """ATTEMPT_ARRIVE when far from stop should return 409."""
        self.stop.state = StopState.EN_ROUTE
        self.stop.save()
        rid = __import__('uuid').uuid4()
        with self.assertRaises(EventProcessingError) as ctx:
            process_event(
                self.user,
                request_id=rid,
                action_type=ActionType.ATTEMPT_ARRIVE,
                stop_id=self.stop.pk,
                payload={'latitude': 19.0, 'longitude': -99.0},
            )
        self.assertEqual(ctx.exception.status_code, 409)
