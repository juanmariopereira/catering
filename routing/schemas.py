"""
Input/output validation for the routes optimize API.
Uses Django REST framework serializers for request/response validation.
"""
from rest_framework import serializers


class LatLngSerializer(serializers.Serializer):
    """Single point: lat, lng."""
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class StopSerializer(serializers.Serializer):
    """Stop with id and coordinates (no Place ID)."""
    id = serializers.JSONField()  # id can be string or number
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class OptimizeRequestSerializer(serializers.Serializer):
    """Request body for POST /api/routes/optimize."""
    start = LatLngSerializer(required=True)
    end = LatLngSerializer(required=False)  # optional; if omitted, end = start
    stops = serializers.ListField(
        child=StopSerializer(),
        max_length=98,
        required=True,
        allow_empty=True,
    )


class LegSerializer(serializers.Serializer):
    """Per-leg distance and duration."""
    distance_meters = serializers.IntegerField(min_value=0)
    duration_seconds = serializers.IntegerField(min_value=0, allow_null=True)


class SummarySerializer(serializers.Serializer):
    """Total distance and duration."""
    total_distance_meters = serializers.IntegerField(min_value=0)
    total_duration_seconds = serializers.IntegerField(min_value=0)


class OptimizeResponseSerializer(serializers.Serializer):
    """Response body for POST /api/routes/optimize."""
    optimized_stop_ids = serializers.ListField(child=serializers.JSONField())
    legs = serializers.ListField(child=LegSerializer())
    polyline = serializers.CharField(allow_null=True)
    summary = SummarySerializer()
