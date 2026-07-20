"""Unit tests for Google Routes matrix normalization used by placement."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.services.routes import route_matrix


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
