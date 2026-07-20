"""Unit tests for the Google Places geocoding adapter."""

import json
import unittest
from unittest.mock import patch

from app.services.places import geocode_place


class GooglePlacesTests(unittest.TestCase):
    """Verify location, coordinate, and hours fields are normalized for activities."""

    @patch("app.services.places.request_places_json")
    def test_geocodes_from_text_search_and_place_details(self, mock_request) -> None:
        """Resolve a place ID first and obtain the final address, coordinates, and hours second."""
        mock_request.side_effect = [
            {"places": [{"id": "test-place", "displayName": {"text": "Original Cafe"}, "formattedAddress": "Old address", "location": {"latitude": 1.3, "longitude": 103.8}}]},
            {"displayName": {"text": "Resolved Cafe"}, "formattedAddress": "1 Bayfront Ave, Singapore", "location": {"latitude": 1.2816, "longitude": 103.8636}, "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9 AM – 6 PM"]}},
        ]

        result = geocode_place("Original Cafe", "Singapore")

        self.assertEqual(result.name, "Resolved Cafe")
        self.assertEqual(result.address, "1 Bayfront Ave, Singapore")
        self.assertEqual(result.latitude, "1.2816")
        self.assertEqual(result.longitude, "103.8636")
        self.assertEqual(json.loads(result.operating_hours or "{}"), {"weekdayDescriptions": ["Monday: 9 AM – 6 PM"]})
        self.assertEqual(mock_request.call_count, 2)
