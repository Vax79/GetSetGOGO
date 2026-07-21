"""Unit tests for Google Routes matrix normalization used by placement."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.services.routes import compute_itinerary_route, compute_route, route_matrix


class RoutesTests(unittest.TestCase):
    """Verify distance and duration route data is usable by the placement algorithm."""

    def mock_response(self, payload: list[dict[str, object]]) -> MagicMock:
        """Build a context-managed HTTP response for a route-matrix JSON payload."""
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        context = MagicMock()
        context.__enter__.return_value = response
        return context

    def test_maps_route_metrics_by_destination_index(self) -> None:
        """Discard no-route elements and retain usable distance and duration values."""
        payload = [
            {"destinationIndex": 0, "condition": "ROUTE_EXISTS", "distanceMeters": 822, "duration": "160s"},
            {"destinationIndex": 1, "condition": "ROUTE_NOT_FOUND"},
        ]
        with patch.dict(os.environ, {"GOOGLE_ROUTES_API_KEY": "test-key"}), patch(
            "app.services.routes.urlopen", return_value=self.mock_response(payload)
        ):
            metrics = route_matrix(("1.3", "103.8"), [("1.2", "103.7"), ("1.4", "103.9")])

        self.assertEqual(metrics[0].distance_meters, 822)
        self.assertEqual(metrics[0].duration_seconds, 160)
        self.assertNotIn(1, metrics)

    def test_reads_encoded_polyline_from_placement_route_response(self) -> None:
        """Retain the encoded Google Routes path for the map instead of recalculating it later."""
        payload = {"routes": [{"distanceMeters": 822, "duration": "160s", "polyline": {"encodedPolyline": "abc123"}}]}
        with patch.dict(os.environ, {"GOOGLE_ROUTES_API_KEY": "test-key"}), patch(
            "app.services.routes.urlopen", return_value=self.mock_response(payload)
        ):
            route = compute_route(("1.3", "103.8"), ("1.2", "103.7"))

        self.assertEqual(route.encoded_polyline, "abc123")
        self.assertEqual(route.distance_meters, 822)
        self.assertEqual(route.duration_seconds, 160)

    def test_reads_every_consecutive_leg_from_one_itinerary_route(self) -> None:
        """Keep per-stop travel estimates aligned with the supplied itinerary order."""
        payload = {
            "routes": [{"legs": [
                {"distanceMeters": 822, "duration": "160s", "polyline": {"encodedPolyline": "first-leg"}},
                {"distanceMeters": 1400, "duration": "300s", "polyline": {"encodedPolyline": "second-leg"}},
            ]}]
        }
        with patch.dict(os.environ, {"GOOGLE_ROUTES_API_KEY": "test-key"}), patch(
            "app.services.routes.urlopen", return_value=self.mock_response(payload)
        ):
            routes = compute_itinerary_route([("1.3", "103.8"), ("1.2", "103.7"), ("1.4", "103.9")])

        self.assertEqual([(route.distance_meters, route.duration_seconds) for route in routes], [(822, 160), (1400, 300)])
        self.assertEqual([route.encoded_polyline for route in routes], ["first-leg", "second-leg"])
