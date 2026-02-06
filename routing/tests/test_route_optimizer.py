"""
Unit tests for route_optimizer: validation (>98 stops, invalid lat/lng)
and optimized stop order mapping from mocked Routes API response.
"""
import unittest
from unittest.mock import patch

from django.test import TestCase, override_settings

from routing.services.route_optimizer import (
    MAX_STOPS,
    RouteOptimizerError,
    optimize_route,
)


@override_settings(GOOGLE_MAPS_API_KEY="test-key")
class RouteOptimizerValidationTests(TestCase):
    """Validation: >98 stops and invalid lat/lng."""

    def test_more_than_98_stops_rejected(self):
        start = {"lat": 40.0, "lng": -3.0}
        stops = [{"id": i, "lat": 40.0 + i * 0.01, "lng": -3.0} for i in range(MAX_STOPS + 1)]
        with self.assertRaises(RouteOptimizerError) as ctx:
            optimize_route(start=start, stops=stops)
        self.assertEqual(ctx.exception.code, "too_many_stops")
        self.assertIn(str(MAX_STOPS), ctx.exception.message)

    def test_invalid_lat_below_rejected(self):
        start = {"lat": -91, "lng": 0}
        stops = [{"id": "a", "lat": 40.0, "lng": -3.0}]
        with self.assertRaises(RouteOptimizerError) as ctx:
            optimize_route(start=start, stops=stops)
        self.assertEqual(ctx.exception.code, "invalid_coords")

    def test_invalid_lat_above_rejected(self):
        start = {"lat": 90.01, "lng": 0}
        stops = [{"id": "a", "lat": 40.0, "lng": -3.0}]
        with self.assertRaises(RouteOptimizerError) as ctx:
            optimize_route(start=start, stops=stops)
        self.assertEqual(ctx.exception.code, "invalid_coords")

    def test_invalid_lng_rejected(self):
        start = {"lat": 40.0, "lng": -181}
        stops = [{"id": "a", "lat": 40.0, "lng": -3.0}]
        with self.assertRaises(RouteOptimizerError) as ctx:
            optimize_route(start=start, stops=stops)
        self.assertEqual(ctx.exception.code, "invalid_coords")

    def test_invalid_stop_lat_rejected(self):
        start = {"lat": 40.0, "lng": -3.0}
        stops = [{"id": "a", "lat": 40.0, "lng": -3.0}, {"id": "b", "lat": 100, "lng": -3.0}]
        with self.assertRaises(RouteOptimizerError) as ctx:
            optimize_route(start=start, stops=stops)
        self.assertEqual(ctx.exception.code, "invalid_coords")


@override_settings(GOOGLE_MAPS_API_KEY="test-key")
class RouteOptimizerMappingTests(TestCase):
    """Mock Routes API response and assert optimized stop order mapping."""

    @patch("routing.services.route_optimizer.compute_routes")
    def test_optimized_order_mapping_from_index(self, mock_compute_routes):
        # API returns optimizedIntermediateWaypointIndex [2, 0, 1] -> visit 3rd, 1st, 2nd
        mock_compute_routes.return_value = {
            "routes": [
                {
                    "optimizedIntermediateWaypointIndex": [2, 0, 1],
                    "legs": [
                        {"distanceMeters": 1000, "duration": "300s"},
                        {"distanceMeters": 2000, "duration": "400s"},
                        {"distanceMeters": 1500, "duration": "350s"},
                        {"distanceMeters": 500, "duration": "120s"},
                    ],
                    "distanceMeters": 5000,
                    "duration": "1170s",
                    "polyline": {"encodedPolyline": "encoded_abc"},
                }
            ]
        }
        start = {"lat": 40.0, "lng": -3.0}
        stops = [
            {"id": "first", "lat": 40.1, "lng": -3.0},
            {"id": "second", "lat": 40.2, "lng": -3.0},
            {"id": "third", "lat": 40.3, "lng": -3.0},
        ]
        result = optimize_route(start=start, stops=stops)
        # Order must be: index 2 -> "third", index 0 -> "first", index 1 -> "second"
        self.assertEqual(result["optimized_stop_ids"], ["third", "first", "second"])
        self.assertEqual(len(result["legs"]), 4)
        self.assertEqual(result["legs"][0]["distance_meters"], 1000)
        self.assertEqual(result["legs"][0]["duration_seconds"], 300)
        self.assertEqual(result["summary"]["total_distance_meters"], 5000)
        self.assertEqual(result["summary"]["total_duration_seconds"], 1170)
        self.assertEqual(result["polyline"], "encoded_abc")

    @patch("routing.services.route_optimizer.compute_routes")
    def test_empty_stops_returns_trivial_result(self, mock_compute_routes):
        start = {"lat": 40.0, "lng": -3.0}
        result = optimize_route(start=start, stops=[])
        self.assertEqual(result["optimized_stop_ids"], [])
        self.assertEqual(result["legs"], [])
        self.assertEqual(result["summary"]["total_distance_meters"], 0)
        self.assertEqual(result["summary"]["total_duration_seconds"], 0)
        mock_compute_routes.assert_not_called()
