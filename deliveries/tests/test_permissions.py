"""
Tests for permission isolation: only courier can access courier context and events.
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from routes.models import Entregador, Ruta, RutaCliente
from contracts.models import Contrato
from clients.models import Cliente
from plans.models import Plan
from deliveries.models import CourierProfile, DeliveryRoute, DeliveryStop, StopState

User = get_user_model()


class CourierPermissionTests(TestCase):
    """Non-courier cannot access courier endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.courier_user = User.objects.create_user(
            username='courier', password='pass', is_staff=False
        )
        self.other_user = User.objects.create_user(
            username='other', password='pass', is_staff=False
        )
        self.entregador = Entregador.objects.create(
            nombre='Courier',
            telefono='+1',
            user=self.courier_user,
            activo=True,
        )
        CourierProfile.objects.create(user=self.courier_user, entregador=self.entregador)
        self.cliente = Cliente.objects.create(nombre='C', telefono='+1')
        self.plan = Plan.objects.create(nombre='P', precio_base=100)
        self.contrato = Contrato.objects.create(
            cliente=self.cliente,
            plan=self.plan,
            fecha_inicio='2025-01-01',
            precio=100,
            latitud='19.432608',
            longitud='-99.133209',
        )
        from django.utils import timezone
        self.ruta = Ruta.objects.create(
            fecha=timezone.localdate(),
            entregador=self.entregador,
            activa=True,
        )
        RutaCliente.objects.create(
            ruta=self.ruta,
            contrato=self.contrato,
            orden_entrega=1,
        )
        self.dr = DeliveryRoute.objects.create(ruta=self.ruta)
        self.stop = DeliveryStop.objects.create(
            delivery_route=self.dr,
            ruta_cliente=self.ruta.ruta_clientes.get(),
            sequence=1,
            state=StopState.PENDING,
        )

    def test_courier_context_requires_auth(self):
        """GET /api/v1/courier/context/ without auth returns 401 or 403 (DRF may return 403)."""
        res = self.client.get('/api/v1/courier/context/')
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_courier_context_requires_courier(self):
        """GET /api/v1/courier/context/ as non-courier returns 403."""
        self.client.force_authenticate(user=self.other_user)
        res = self.client.get('/api/v1/courier/context/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_courier_context_ok_for_courier(self):
        """GET /api/v1/courier/context/ as courier returns 200."""
        self.client.force_authenticate(user=self.courier_user)
        res = self.client.get('/api/v1/courier/context/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('profile', res.json())
        self.assertIn('route', res.json())

    def test_events_require_courier(self):
        """POST /api/v1/events/ as non-courier returns 403."""
        self.client.force_authenticate(user=self.other_user)
        res = self.client.post(
            '/api/v1/events/',
            data={
                'request_id': str(uuid.uuid4()),
                'type': 'LOCATION_PING',
                'payload': {'latitude': 19.0, 'longitude': -99.0},
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_mobile_version_public(self):
        """GET /api/v1/mobile/version/ does not require auth."""
        res = self.client.get('/api/v1/mobile/version/?platform=ANDROID')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
