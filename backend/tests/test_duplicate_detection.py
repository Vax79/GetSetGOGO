"""Tests for normalized-name duplicate protection before and during approval."""

import unittest

from app.routers.enrichment import unique_new_candidates
from app.services.gemini import ExtractedActivity


class DuplicateDetectionTests(unittest.TestCase):
    """Confirm duplicate activity names never reach the review-and-approval flow."""

    def test_discards_existing_and_repeated_normalized_names(self) -> None:
        """Ignore punctuation/case variants both against saved activities and extraction siblings."""
        candidates = [
            ExtractedActivity("Eat at Cafe!", "food", "Cafe", None, None),
            ExtractedActivity("EAT AT CAFE", "food", "Cafe", None, None),
            ExtractedActivity("Visit museum", "sightseeing", "Museum", None, None),
        ]

        filtered = unique_new_candidates(candidates, {"eatatcafe"})

        self.assertEqual([candidate.activity_name for candidate in filtered], ["Visit museum"])
