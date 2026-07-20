"""Unit tests for Gemini's structured extraction and enrichment boundary."""

import unittest
from unittest.mock import patch

from app.services.gemini import GeminiError, enrich_activity_data, extract_activities, interaction_output


class GeminiServiceTests(unittest.TestCase):
    """Verify that only complete structured model data reaches application code."""

    @patch("app.services.gemini.call_gemini_json")
    def test_extracts_individual_activity_and_place_fields(self, mock_call) -> None:
        """Convert Gemini's activity list into candidates with practical place fields."""
        mock_call.return_value = {
            "activities": [
                {
                    "activity_name": "Eat ramen",
                    "category": "food",
                    "poi_name": "Ramen Street",
                    "poi_address": "Shinjuku, Tokyo",
                }
            ]
        }

        candidates = extract_activities("Tokyo", "Best ramen", "Visit Ramen Street.")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].activity_name, "Eat ramen")
        self.assertEqual(candidates[0].poi_name, "Ramen Street")

    def test_reads_rest_interaction_model_output(self) -> None:
        """Read text returned in the raw REST response's model-output step."""
        payload = {"steps": [{"type": "thought"}, {"type": "model_output", "content": [{"type": "text", "text": "{\"activities\": []}"}]}]}

        self.assertEqual(interaction_output(payload), '{"activities": []}')

    @patch("app.services.gemini.call_gemini_json")
    def test_rejects_incomplete_extracted_activity(self, mock_call) -> None:
        """Reject a model response that omits a required candidate field."""
        mock_call.return_value = {"activities": [{"activity_name": "Eat ramen", "category": "food"}]}

        with self.assertRaises(GeminiError):
            extract_activities("Tokyo", "Best ramen", None)

    @patch("app.services.gemini.call_gemini_json")
    def test_returns_all_three_enrichment_sections(self, mock_call) -> None:
        """Keep practical enrichment grouped under the user-requested headings."""
        mock_call.return_value = {
            "food_and_consumption": {"summary": "Ramen specialist.", "recommendations": ["Ask about broth."]},
            "practical_visiting_information": {"summary": "Check before visiting.", "details": []},
            "vibe_context_highlights": {"summary": "Compact and lively.", "highlights": ["Counter seating."]},
        }

        enrichment = enrich_activity_data("Eat ramen", "Shinjuku", "Tokyo")

        self.assertEqual(set(enrichment), {"food_and_consumption", "practical_visiting_information", "vibe_context_highlights"})
