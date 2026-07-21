"""Unit tests for the Google Places geocoding adapter."""

import json
import unittest
from unittest.mock import patch

from app.services.places import geocode_place, search_places


class GooglePlacesTests(unittest.TestCase):
    """Verify location, coordinate, and hours fields are normalized for activities."""

    @patch("app.services.places.request_places_json")
    def test_geocodes_from_one_text_search_response(self, mock_request) -> None:
        """Use Text Search's response fields instead of a second Place Details request."""
        mock_request.return_value = {
            "places": [{"displayName": {"text": "Resolved Cafe"}, "formattedAddress": "1 Bayfront Ave, Singapore", "location": {"latitude": 1.2816, "longitude": 103.8636}, "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9 AM – 6 PM"]}}]
        }

        result = geocode_place("Original Cafe", "Singapore")

        self.assertEqual(result.name, "Resolved Cafe")
        self.assertEqual(result.address, "1 Bayfront Ave, Singapore")
        self.assertEqual(result.latitude, "1.2816")
        self.assertEqual(result.longitude, "103.8636")
        self.assertEqual(json.loads(result.operating_hours or "{}"), {"weekdayDescriptions": ["Monday: 9 AM – 6 PM"]})
        self.assertEqual(mock_request.call_count, 1)

    @patch("app.services.places.request_places_json")
    def test_returns_multiple_selectable_matches_for_manual_search(self, mock_request) -> None:
        """Expose a concise set of geocoded Google Maps choices to manual entries."""
        mock_request.return_value = {
            "places": [
                {"displayName": {"text": "Cafe One"}, "formattedAddress": "1 Orchard Rd, Singapore", "location": {"latitude": 1.304, "longitude": 103.832}},
                {"displayName": {"text": "Cafe Two"}, "formattedAddress": "2 Orchard Rd, Singapore", "location": {"latitude": 1.305, "longitude": 103.833}},
            ]
        }

        results = search_places("Cafe", "Singapore")

        self.assertEqual([result.name for result in results], ["Cafe One", "Cafe Two"])
        self.assertEqual(results[1].longitude, "103.833")
