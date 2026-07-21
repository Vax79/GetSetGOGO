"""Tests for using previewed TikTok context in the extraction request."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.routers.enrichment import extract_tiktok_activities
from app.schemas import ExtractActivitiesRequest
from app.services.gemini import ExtractedActivity
from app.services.places import GeocodedPlace


class ExtractionTests(unittest.TestCase):
    """Confirm a previewed caption avoids a second ScrapeBadger lookup."""

    @patch("app.routers.enrichment.require_trip")
    @patch("app.routers.enrichment.geocode_place")
    @patch("app.routers.enrichment.extract_activities")
    @patch("app.routers.enrichment.fetch_tiktok_transcript")
    @patch("app.routers.enrichment.fetch_tiktok_metadata")
    def test_uses_previewed_caption_without_refetching_tiktok(
        self,
        mock_metadata: MagicMock,
        mock_transcript: MagicMock,
        mock_extract: MagicMock,
        mock_geocode: MagicMock,
        mock_trip: MagicMock,
    ) -> None:
        """Send preview data directly into Gemini while keeping the TikTok URL validated."""
        mock_trip.return_value = SimpleNamespace(destination_city="Shanghai", destination_region=None)
        mock_extract.return_value = [ExtractedActivity("Visit Metal Hands", ["Food", "Culture"], "Metal Hands", None, None)]
        mock_geocode.return_value = GeocodedPlace("Metal Hands", "Shanghai", "31.2", "121.4", None)
        database = MagicMock()
        database.query.return_value.filter_by.return_value = []
        payload = ExtractActivitiesRequest(
            source_url="https://www.tiktok.com/@creator/video/123",
            caption="Five Shanghai cafes to save.",
        )

        response = extract_tiktok_activities(1, payload, database)

        mock_metadata.assert_not_called()
        mock_transcript.assert_not_called()
        mock_extract.assert_called_once_with("Shanghai", "Five Shanghai cafes to save.", None)
        self.assertEqual(response.activities[0].source_url, payload.source_url)
