"""
Serializers for deliveries API.
"""
from rest_framework import serializers
from .models import CourierProfile, DeliveryRoute, DeliveryStop, MobileAppVersion


class CourierProfileSerializer(serializers.ModelSerializer):
    """Courier profile for context response."""
    entregador_name = serializers.CharField(source='entregador.nombre', read_only=True)
    entregador_id = serializers.PrimaryKeyRelatedField(
        source='entregador', read_only=True
    )

    class Meta:
        model = CourierProfile
        fields = ['id', 'entregador_id', 'entregador_name']


class DeliveryStopSerializer(serializers.ModelSerializer):
    """Stop with server-driven allowed_actions (from context, not from model)."""
    codigo_entrega = serializers.CharField(source='ruta_cliente.codigo_entrega', read_only=True)
    address = serializers.SerializerMethodField()
    can_mark_arrived = serializers.BooleanField(read_only=True, default=False)
    can_mark_delivered = serializers.BooleanField(read_only=True, default=False)
    can_mark_failed = serializers.BooleanField(read_only=True, default=False)
    reason_if_blocked = serializers.CharField(read_only=True, default=None, allow_null=True)

    class Meta:
        model = DeliveryStop
        fields = [
            'id', 'sequence', 'state', 'ruta_cliente', 'codigo_entrega',
            'address', 'can_mark_arrived', 'can_mark_delivered', 'can_mark_failed',
            'reason_if_blocked',
        ]

    def get_address(self, obj):
        try:
            return obj.ruta_cliente.contrato.direccion_entrega or ''
        except Exception:
            return ''


class CourierContextSerializer(serializers.Serializer):
    """Response for GET /courier/context/."""
    profile = CourierProfileSerializer()
    route = serializers.DictField(allow_null=True)
    stops = serializers.ListField(child=serializers.DictField())
    current_active_stop_id = serializers.IntegerField(allow_null=True)
    next_stop_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    current_active_stop = serializers.DictField(allow_null=True)
    next_stop = serializers.DictField(allow_null=True)


class EventRequestSerializer(serializers.Serializer):
    """Request body for POST /events/."""
    request_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=[
        'LOCATION_PING', 'ATTEMPT_ARRIVE', 'ATTEMPT_DELIVER', 'ATTEMPT_FAIL', 'ATTEMPT_CORRECT',
    ])
    stop_id = serializers.IntegerField(required=False, allow_null=True)
    payload = serializers.JSONField(required=False, default=dict)


class MobileVersionSerializer(serializers.ModelSerializer):
    """Mobile app version for version check endpoint."""
    update_required = serializers.SerializerMethodField()
    apk_url = serializers.URLField(allow_blank=True)

    class Meta:
        model = MobileAppVersion
        fields = [
            'platform', 'version_code', 'min_version_code',
            'update_required', 'apk_url', 'release_notes',
        ]

    def get_update_required(self, obj):
        current = self.context.get('current_version_code')
        if current is None:
            return False
        return int(current) < obj.min_version_code
