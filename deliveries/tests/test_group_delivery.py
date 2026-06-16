"""
Tests para la feature de agrupamiento de entregas por PuntoEntrega.

Verifica:
- ATTEMPT_ARRIVE en un stop de grupo → todos los stops del grupo pasan a DELIVERED.
- Stop sin grupo → comportamiento individual sin cambios.
- ATTEMPT_CORRECT: DELIVERED → FAILED y FAILED → DELIVERED.
- El contexto API incluye 'grupos' y cada stop incluye 'punto_entrega'.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from routes.models import Entregador, Ruta, RutaCliente, PuntoEntrega
from contracts.models import Contrato
from clients.models import Cliente
from plans.models import Plan

from deliveries.models import (
    CourierProfile, DeliveryRoute, DeliveryStop, StopState, ActionType,
    DeliveryActionEvent,
)
from deliveries.services.event_processor import process_event

User = get_user_model()


class GroupDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='courier_grp', password='x', is_staff=False)
        self.entregador = Entregador.objects.create(
            nombre='Courier Grupo', telefono='+1', user=self.user, activo=True,
        )
        CourierProfile.objects.create(user=self.user, entregador=self.entregador)
        self.cliente1 = Cliente.objects.create(nombre='Cli1', telefono='+2')
        self.cliente2 = Cliente.objects.create(nombre='Cli2', telefono='+3')
        self.cliente3 = Cliente.objects.create(nombre='Cli3', telefono='+4')
        self.plan = Plan.objects.create(nombre='Plan Grp', precio_base=100)

        # PuntoEntrega compartido
        self.pe = PuntoEntrega.objects.create(
            nombre='Edificio Torres',
            latitud=Decimal('19.432608'),
            longitud=Decimal('-99.133209'),
            notas_acceso='Cit. 301',
        )

        self.c1 = Contrato.objects.create(
            cliente=self.cliente1, plan=self.plan, fecha_inicio='2025-01-01', precio=100,
            latitud=Decimal('19.432608'), longitud=Decimal('-99.133209'),
            punto_entrega=self.pe,
        )
        self.c2 = Contrato.objects.create(
            cliente=self.cliente2, plan=self.plan, fecha_inicio='2025-01-01', precio=100,
            latitud=Decimal('19.432608'), longitud=Decimal('-99.133209'),
            punto_entrega=self.pe,
        )
        self.c3 = Contrato.objects.create(
            cliente=self.cliente3, plan=self.plan, fecha_inicio='2025-01-01', precio=100,
            latitud=Decimal('19.432608'), longitud=Decimal('-99.133209'),
            punto_entrega=self.pe,
        )

        self.ruta = Ruta.objects.create(
            fecha=timezone.localdate(), entregador=self.entregador, activa=True,
        )
        self.rc1 = RutaCliente.objects.create(ruta=self.ruta, contrato=self.c1, orden_entrega=1)
        self.rc2 = RutaCliente.objects.create(ruta=self.ruta, contrato=self.c2, orden_entrega=2)
        self.rc3 = RutaCliente.objects.create(ruta=self.ruta, contrato=self.c3, orden_entrega=3)

        self.delivery_route = DeliveryRoute.objects.create(ruta=self.ruta)
        self.s1 = DeliveryStop.objects.create(
            delivery_route=self.delivery_route, ruta_cliente=self.rc1,
            sequence=1, state=StopState.EN_ROUTE,
        )
        self.s2 = DeliveryStop.objects.create(
            delivery_route=self.delivery_route, ruta_cliente=self.rc2,
            sequence=2, state=StopState.EN_ROUTE,
        )
        self.s3 = DeliveryStop.objects.create(
            delivery_route=self.delivery_route, ruta_cliente=self.rc3,
            sequence=3, state=StopState.EN_ROUTE,
        )

    # -----------------------------------------------------------------------
    # 1. Auto-entrega del grupo completo
    # -----------------------------------------------------------------------

    def test_arrive_en_stop_de_grupo_marca_todos_delivered(self):
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.s1.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )
        for s in [self.s1, self.s2, self.s3]:
            s.refresh_from_db()
            self.assertEqual(s.state, StopState.DELIVERED, f'Stop {s.pk} debería ser DELIVERED')

    def test_arrive_en_grupo_sincroniza_ruta_cliente_entregada(self):
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.s1.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )
        for rc in [self.rc1, self.rc2, self.rc3]:
            rc.refresh_from_db()
            self.assertTrue(rc.entregada, f'RutaCliente {rc.pk} debería quedar entregada')

    def test_arrive_en_grupo_registra_eventos_auto_grupo(self):
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.s1.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )
        # Los hermanos deben tener evento ATTEMPT_DELIVER con auto_grupo=True
        for s in [self.s2, self.s3]:
            ev = DeliveryActionEvent.objects.filter(
                stop=s, action_type=ActionType.ATTEMPT_DELIVER,
            ).first()
            self.assertIsNotNone(ev, f'Falta evento ATTEMPT_DELIVER en stop {s.pk}')
            self.assertTrue(ev.payload.get('auto_grupo'), f'Falta auto_grupo en stop {s.pk}')

    # -----------------------------------------------------------------------
    # 2. Stop sin grupo — comportamiento individual sin cambios
    # -----------------------------------------------------------------------

    def test_arrive_sin_grupo_solo_marca_el_stop_solicitado(self):
        # Crear contrato sin punto_entrega
        cliente_solo = Cliente.objects.create(nombre='Solo', telefono='+9')
        contrato_solo = Contrato.objects.create(
            cliente=cliente_solo, plan=self.plan, fecha_inicio='2025-01-01', precio=100,
            latitud=Decimal('19.432608'), longitud=Decimal('-99.133209'),
        )
        rc_solo = RutaCliente.objects.create(
            ruta=self.ruta, contrato=contrato_solo, orden_entrega=4,
        )
        stop_solo = DeliveryStop.objects.create(
            delivery_route=self.delivery_route, ruta_cliente=rc_solo,
            sequence=4, state=StopState.EN_ROUTE,
        )

        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=stop_solo.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )
        stop_solo.refresh_from_db()
        # Solo debe quedar ARRIVED (no DELIVERED, ya que no hay grupo)
        self.assertEqual(stop_solo.state, StopState.ARRIVED)
        # Los otros stops del grupo no deben haberse afectado
        for s in [self.s1, self.s2, self.s3]:
            s.refresh_from_db()
            self.assertEqual(s.state, StopState.EN_ROUTE)

    # -----------------------------------------------------------------------
    # 3. ATTEMPT_CORRECT: correcciones post-entrega
    # -----------------------------------------------------------------------

    def _entregar_grupo(self):
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_ARRIVE,
            stop_id=self.s1.pk,
            payload={'latitude': 19.432608, 'longitude': -99.133209},
        )

    def test_attempt_correct_delivered_to_failed(self):
        self._entregar_grupo()
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.state, StopState.DELIVERED)

        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_CORRECT,
            stop_id=self.s2.pk,
            payload={'new_state': 'FAILED', 'reason': 'No estaba en casa'},
        )
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.state, StopState.FAILED)
        self.rc2.refresh_from_db()
        self.assertTrue(self.rc2.no_entregada)
        self.assertEqual(self.rc2.motivo_no_entrega, 'No estaba en casa')

    def test_attempt_correct_failed_to_delivered(self):
        self._entregar_grupo()
        # Primero corrijo a FAILED
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_CORRECT,
            stop_id=self.s2.pk,
            payload={'new_state': 'FAILED', 'reason': 'No estaba'},
        )
        # Luego corrijo de vuelta a DELIVERED
        process_event(
            self.user,
            request_id=uuid.uuid4(),
            action_type=ActionType.ATTEMPT_CORRECT,
            stop_id=self.s2.pk,
            payload={'new_state': 'DELIVERED'},
        )
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.state, StopState.DELIVERED)
        self.rc2.refresh_from_db()
        self.assertTrue(self.rc2.entregada)

    def test_attempt_correct_estado_invalido_retorna_400(self):
        self._entregar_grupo()
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.post('/api/v1/events/', {
            'request_id': str(uuid.uuid4()),
            'type': 'ATTEMPT_CORRECT',
            'stop_id': self.s1.pk,
            'payload': {'new_state': 'EN_ROUTE'},
        }, format='json')
        self.assertEqual(res.status_code, 400)

    # -----------------------------------------------------------------------
    # 4. Contexto API incluye 'grupos' y 'punto_entrega' por stop
    # -----------------------------------------------------------------------

    def test_contexto_incluye_grupos(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/api/v1/courier/context/')
        self.assertEqual(res.status_code, 200)
        grupos = res.data.get('grupos', [])
        self.assertEqual(len(grupos), 1)
        g = grupos[0]
        self.assertEqual(g['nombre'], 'Edificio Torres')
        self.assertEqual(set(g['stop_ids']), {self.s1.pk, self.s2.pk, self.s3.pk})

    def test_cada_stop_incluye_punto_entrega(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/api/v1/courier/context/')
        self.assertEqual(res.status_code, 200)
        for stop_data in res.data['stops']:
            pe = stop_data.get('punto_entrega')
            self.assertIsNotNone(pe)
            self.assertEqual(pe['id'], self.pe.pk)
            self.assertEqual(pe['notas_acceso'], 'Cit. 301')
