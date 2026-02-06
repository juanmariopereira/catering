"""
Tests for POST /api/routes/optimize: validation errors and success with mocked optimizer.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from routing.services.route_optimizer import RouteOptimizerError


@override_settings(GOOGLE_MAPS_API_KEY="test-key")
class RouteOptimizeEndpointTests(TestCase):
    """API endpoint: >98 stops rejected, invalid coords rejected, success returns 200."""

    def setUp(self):
        self.client = APIClient()

    def test_more_than_98_stops_returns_400(self):
        start = {"lat": 40.0, "lng": -3.0}
        stops = [{"id": i, "lat": 40.0, "lng": -3.0} for i in range(99)]
        resp = self.client.post(
            "/api/routes/optimize",
            {"start": start, "stops": stops},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        self.assertIn("error", data)
        self.assertTrue(
            data.get("error") in ("validation_error", "too_many_stops"),
            f"expected validation or too_many_stops, got {data}",
        )

    def test_invalid_lat_in_body_returns_400(self):
        resp = self.client.post(
            "/api/routes/optimize",
            {
                "start": {"lat": 95, "lng": -3.0},
                "stops": [{"id": "a", "lat": 40.0, "lng": -3.0}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        self.assertIn("error", data)

    def test_missing_start_returns_400(self):
        resp = self.client.post(
            "/api/routes/optimize",
            {"stops": [{"id": "a", "lat": 40.0, "lng": -3.0}]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("routing.views.optimize_route")
    def test_success_returns_200_and_optimized_order(self, mock_optimize_route):
        mock_optimize_route.return_value = {
            "optimized_stop_ids": ["c", "a", "b"],
            "legs": [
                {"distance_meters": 1000, "duration_seconds": 300},
                {"distance_meters": 2000, "duration_seconds": 400},
                {"distance_meters": 500, "duration_seconds": 120},
            ],
            "polyline": "enc_poly",
            "summary": {"total_distance_meters": 3500, "total_duration_seconds": 820},
        }
        resp = self.client.post(
            "/api/routes/optimize",
            {
                "start": {"lat": 40.0, "lng": -3.0},
                "stops": [
                    {"id": "a", "lat": 40.1, "lng": -3.0},
                    {"id": "b", "lat": 40.2, "lng": -3.0},
                    {"id": "c", "lat": 40.3, "lng": -3.0},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["optimized_stop_ids"], ["c", "a", "b"])
        self.assertEqual(len(data["legs"]), 3)
        self.assertEqual(data["summary"]["total_distance_meters"], 3500)
        self.assertEqual(data["polyline"], "enc_poly")

    @patch("routing.views.optimize_route")
    def test_optimizer_api_error_returns_502(self, mock_optimize_route):
        mock_optimize_route.side_effect = RouteOptimizerError("Quota exceeded", "api_error")
        resp = self.client.post(
            "/api/routes/optimize",
            {
                "start": {"lat": 40.0, "lng": -3.0},
                "stops": [{"id": "a", "lat": 40.0, "lng": -3.0}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        data = resp.json()
        self.assertEqual(data.get("error"), "api_error")
