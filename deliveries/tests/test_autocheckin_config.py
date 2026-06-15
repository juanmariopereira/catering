"""
Tests para la configuración de seguimiento (sistema + por entregador),
el check-in automático por GPS y el endpoint de config.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from routes.models import Entregador, Ruta, RutaCliente
from contracts.models import Contrato
from clients.models import Cliente
from plans.models import Plan

from deliveries.models import (
    CourierProfile, DeliveryRoute, DeliveryStop, StopState, ActionType,
    DeliveryActionEvent,
)
from deliveries.services.event_processor import process_event
from deliveries.services.courier_config import resolver_config

User = get_user_model()


class CheckinConfigTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='courier_cfg', password='x', is_staff=False)
        self.entregador = Entregador.objects.create(
            nombre='Courier Cfg', telefono='+1', user=self.user, activo=True,
        )
        CourierProfile.objects.create(user=self.user, entregador=self.entregador)
        self.cliente = Cliente.objects.create(nombre='Cli', telefono='+2')
        self.plan = Plan.objects.create(nombre='Plan Cfg', precio_base=100)
        self.contrato = Contrato.objects.create(
            cliente=self.cliente, plan=self.plan, fecha_inicio='2025-01-01', precio=100,
            latitud=Decimal('19.432608'), longitud=Decimal('-99.133209'),
        )
        self.ruta = Ruta.objects.create(fecha=timezone.localdate(), entregador=self.entregador, activa=True)
        self.ruta_cliente = RutaCliente.objects.create(ruta=self.ruta, contrato=self.contrato, orden_entrega=1)
        self.delivery_route = DeliveryRoute.objects.create(ruta=self.ruta)
        self.stop = DeliveryStop.objects.create(
            delivery_route=self.delivery_route, ruta_cliente=self.ruta_cliente,
            sequence=1, state=StopState.EN_ROUTE,
        )

    def _ping_at_stop(self):
        process_event(
            self.user, request_id=uuid.uuid4(), action_type=ActionType.LOCATION_PING,
            payload={'latitude': float(self.contrato.latitud), 'longitude': float(self.contrato.longitud)},
        )

    # --- Resolver de config (sistema vs override por entregador) ---

    def test_config_defaults_sistema(self):
        cfg = resolver_config(self.entregador)
        self.assertEqual(cfg['auto_checkin'], False)   # seeded 'false'
        self.assertEqual(cfg['radio_metros'], 150)     # seeded 150
        self.assertEqual(cfg['ping_segundos'], 5)      # seeded 5

    def test_override_por_entregador(self):
        self.entregador.checkin_auto = True
        self.entregador.checkin_radio_metros = 500
        self.entregador.ping_intervalo_segundos = 10
        self.entregador.save()
        cfg = resolver_config(self.entregador)
        self.assertEqual(cfg['auto_checkin'], True)
        self.assertEqual(cfg['radio_metros'], 500)
        self.assertEqual(cfg['ping_segundos'], 10)

    # --- Check-in automático por GPS ---

    def test_autocheckin_off_por_defecto_no_marca_llegada(self):
        self._ping_at_stop()
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.EN_ROUTE)

    def test_autocheckin_on_marca_llegada_dentro_del_radio(self):
        self.entregador.checkin_auto = True
        self.entregador.save()
        self._ping_at_stop()
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.ARRIVED)
        # Queda registrado como evento automático
        ev = DeliveryActionEvent.objects.filter(stop=self.stop, action_type=ActionType.ATTEMPT_ARRIVE).first()
        self.assertIsNotNone(ev)
        self.assertTrue(ev.payload.get('auto'))

    def test_autocheckin_on_pero_lejos_no_marca(self):
        self.entregador.checkin_auto = True
        self.entregador.checkin_radio_metros = 100
        self.entregador.save()
        process_event(
            self.user, request_id=uuid.uuid4(), action_type=ActionType.LOCATION_PING,
            payload={'latitude': 19.0, 'longitude': -99.0},  # lejos
        )
        self.stop.refresh_from_db()
        self.assertEqual(self.stop.state, StopState.EN_ROUTE)

    # --- Endpoint de config ---

    def test_config_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/api/v1/courier/config/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('auto_checkin', res.data)
        self.assertIn('radio_metros', res.data)
        self.assertIn('ping_segundos', res.data)
