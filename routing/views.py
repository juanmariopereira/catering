"""
API view for route optimization (POST /api/routes/optimize).
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .schemas import OptimizeRequestSerializer, OptimizeResponseSerializer
from .services.route_optimizer import RouteOptimizerError, optimize_route

logger = logging.getLogger(__name__)


class RouteOptimizeView(APIView):
    """
    POST /api/routes/optimize
    Body: { "start": { "lat", "lng" }, "end": { "lat", "lng" } (optional), "stops": [ { "id", "lat", "lng" }, ... ] }
    Returns: optimized_stop_ids, legs, polyline, summary.
    """

    def post(self, request):
        # Validate request body
        ser = OptimizeRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"error": "validation_error", "details": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = ser.validated_data
        start = data["start"]
        end = data.get("end")  # None means use start as end
        stops = data["stops"]

        try:
            result = optimize_route(start=start, stops=stops, end=end)
        except RouteOptimizerError as e:
            code = getattr(e, "code", "error")
            if code == "too_many_stops":
                status_code = status.HTTP_400_BAD_REQUEST
            elif code in ("invalid_input", "invalid_coords", "config"):
                status_code = status.HTTP_400_BAD_REQUEST
            else:
                status_code = status.HTTP_502_BAD_GATEWAY  # API/upstream error
            return Response(
                {"error": code, "message": e.message},
                status=status_code,
            )

        # Response matches OptimizeResponseSerializer shape
        out_ser = OptimizeResponseSerializer(data=result)
        if not out_ser.is_valid():
            logger.warning("Optimize response validation failed: %s", out_ser.errors)
            return Response(result, status=status.HTTP_200_OK)
        return Response(out_ser.validated_data, status=status.HTTP_200_OK)
