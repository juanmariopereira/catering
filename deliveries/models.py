"""
Delivery domain models for the courier API.
All business state lives here; mobile app only sends events and renders API data.
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class StopState:
    """Stop state machine states. Transitions enforced server-side."""
    PENDING = 'PENDING'
    EN_ROUTE = 'EN_ROUTE'
    ARRIVED = 'ARRIVED'
    DELIVERED = 'DELIVERED'
    FAILED = 'FAILED'

    CHOICES = [
        (PENDING, 'Pending'),
        (EN_ROUTE, 'En route'),
        (ARRIVED, 'Arrived'),
        (DELIVERED, 'Delivered'),
        (FAILED, 'Failed'),
    ]

    VALID_TRANSITIONS = {
        PENDING: [EN_ROUTE],
        EN_ROUTE: [ARRIVED, FAILED],
        ARRIVED: [DELIVERED, FAILED],
        DELIVERED: [FAILED],   # corrección post-entrega
        FAILED: [DELIVERED],   # corrección post-fallo
    }


class ActionType:
    """Event action types from mobile. Processed server-side only."""
    LOCATION_PING = 'LOCATION_PING'
    ATTEMPT_ARRIVE = 'ATTEMPT_ARRIVE'
    ATTEMPT_DELIVER = 'ATTEMPT_DELIVER'
    ATTEMPT_FAIL = 'ATTEMPT_FAIL'
    ATTEMPT_CORRECT = 'ATTEMPT_CORRECT'  # corrección bidireccional DELIVERED↔FAILED

    CHOICES = [
        (LOCATION_PING, 'Location ping'),
        (ATTEMPT_ARRIVE, 'Attempt arrive'),
        (ATTEMPT_DELIVER, 'Attempt deliver'),
        (ATTEMPT_FAIL, 'Attempt fail'),
        (ATTEMPT_CORRECT, 'Attempt correct'),
    ]


class CourierProfile(models.Model):
    """Links a User to an Entregador (courier). Used for API auth and route access."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courier_profile',
        verbose_name='User',
    )
    entregador = models.OneToOneField(
        'routes.Entregador',
        on_delete=models.PROTECT,
        related_name='courier_profile',
        verbose_name='Entregador',
        help_text='Courier identity in the routes app.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Courier profile'
        verbose_name_plural = 'Courier profiles'

    def __str__(self):
        return f"CourierProfile({self.user.username} -> {self.entregador.nombre})"


class DeliveryRoute(models.Model):
    """API-facing route for a day. One-to-one with routes.Ruta for the courier's route."""
    ruta = models.OneToOneField(
        'routes.Ruta',
        on_delete=models.CASCADE,
        related_name='delivery_route',
        verbose_name='Ruta',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery route'
        verbose_name_plural = 'Delivery routes'

    def __str__(self):
        return f"DeliveryRoute({self.ruta})"

    @property
    def date(self):
        return self.ruta.fecha

    @property
    def courier_entregador(self):
        return self.ruta.entregador


class DeliveryStop(models.Model):
    """A stop on a delivery route with server-driven state. Links to RutaCliente."""
    delivery_route = models.ForeignKey(
        DeliveryRoute,
        on_delete=models.CASCADE,
        related_name='stops',
        verbose_name='Delivery route',
    )
    ruta_cliente = models.OneToOneField(
        'routes.RutaCliente',
        on_delete=models.CASCADE,
        related_name='delivery_stop',
        verbose_name='Ruta cliente',
    )
    state = models.CharField(
        max_length=20,
        choices=StopState.CHOICES,
        default=StopState.PENDING,
        db_index=True,
    )
    sequence = models.PositiveIntegerField(
        help_text='Order in route (from RutaCliente.orden_entrega).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery stop'
        verbose_name_plural = 'Delivery stops'
        ordering = ['delivery_route', 'sequence']
        unique_together = [['delivery_route', 'ruta_cliente']]

    def __str__(self):
        return f"Stop #{self.sequence} ({self.state}) on {self.delivery_route}"

    def can_transition_to(self, new_state):
        allowed = StopState.VALID_TRANSITIONS.get(self.state, [])
        return new_state in allowed


class CourierLocationPing(models.Model):
    """Courier GPS ping. Backend uses this for proximity and active-stop calculation."""
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='location_pings',
        verbose_name='Courier (user)',
    )
    delivery_route = models.ForeignKey(
        DeliveryRoute,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='location_pings',
        verbose_name='Route',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Courier location ping'
        verbose_name_plural = 'Courier location pings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['courier', '-created_at']),
        ]


class DeliveryActionEvent(models.Model):
    """Immutable log of courier actions. State changes are derived from processing these."""
    request_id = models.UUIDField(unique=True, db_index=True, editable=False)
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_action_events',
        verbose_name='Courier',
    )
    stop = models.ForeignKey(
        DeliveryStop,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='action_events',
        verbose_name='Stop',
    )
    action_type = models.CharField(max_length=30, choices=ActionType.CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Delivery action event'
        verbose_name_plural = 'Delivery action events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['courier', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.request_id:
            self.request_id = uuid.uuid4()
        super().save(*args, **kwargs)


class DeliveryEventOutbox(models.Model):
    """Outbox for integration events (e.g. customer notifications). Backend emits; mobile does not."""
    EVENT_EN_ROUTE = 'stop_en_route'
    EVENT_DELIVERED = 'stop_delivered'
    EVENT_FAILED = 'stop_failed'

    event_type = models.CharField(max_length=50)
    stop = models.ForeignKey(
        DeliveryStop,
        on_delete=models.CASCADE,
        related_name='outbox_events',
        verbose_name='Stop',
    )
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Delivery event outbox'
        verbose_name_plural = 'Delivery event outbox'
        ordering = ['-created_at']


class MobileAppVersion(models.Model):
    """Minimum version and APK URL for mobile clients."""
    platform = models.CharField(max_length=20)  # ANDROID, etc.
    version_code = models.PositiveIntegerField(
        help_text='Current app version code (e.g. 123).',
    )
    min_version_code = models.PositiveIntegerField(
        help_text='Minimum required version; clients below this should update.',
    )
    apk_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL to download APK when update is required.',
    )
    release_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mobile app version'
        verbose_name_plural = 'Mobile app versions'
        ordering = ['-version_code']
        unique_together = [['platform', 'version_code']]
