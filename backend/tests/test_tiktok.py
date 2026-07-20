import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.services.tiktok import (
    TikTokMetadataError,
    TikTokTranscriptUnavailable,
    extract_video_id,
    fetch_tiktok_metadata,
    fetch_tiktok_transcript,
    resolve_tiktok_url,
    validate_tiktok_url,
)


class TikTokMetadataTests(unittest.TestCase):
    """Verify ScrapeBadger response normalization without reaching the live provider."""

    def mock_response(self, payload: dict[str, object]) -> MagicMock:
        """Build a context-managed URL response containing a JSON provider payload."""
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        context = MagicMock()
        context.__enter__.return_value = response
        return context

    def test_fetches_video_detail_metadata(self) -> None:
        """Convert a ScrapeBadger video-detail payload into the metadata preview shape."""
        payload = {
            "video": {
                "description": "Dinner in Singapore #Food #Travel",
                "share_url": "https://www.tiktok.com/@jetsetter/video/123",
                "hashtags": ["Food", "Travel"],
                "author": {"unique_id": "jetsetter", "nickname": "Jet Setter"},
                "video": {"cover": "https://cdn.example/cover.jpg"},
            }
        }
        with patch.dict(os.environ, {"SCRAPEBADGER_API_KEY": "test-key"}), patch(
            "app.services.tiktok.urlopen", return_value=self.mock_response(payload)
        ):
            metadata = fetch_tiktok_metadata("https://www.tiktok.com/@jetsetter/video/123")

        self.assertEqual(metadata.caption, "Dinner in Singapore #Food #Travel")
        self.assertEqual(metadata.hashtags, ["Food", "Travel"])
        self.assertEqual(metadata.author_name, "Jet Setter")
        self.assertEqual(metadata.thumbnail_url, "https://cdn.example/cover.jpg")

    def test_fetches_full_speech_to_text_transcript(self) -> None:
        """Join timestamped ScrapeBadger ASR segments when no combined transcript text is returned."""
        payload = {"voice_to_text": [{"start": 0, "end": 1, "text": "Try this cafe."}, {"start": 1, "end": 2, "text": "It is excellent."}]}
        with patch.dict(os.environ, {"SCRAPEBADGER_API_KEY": "test-key"}), patch(
            "app.services.tiktok.urlopen", return_value=self.mock_response(payload)
        ):
            transcript = fetch_tiktok_transcript("https://www.tiktok.com/@jetsetter/video/123")

        self.assertEqual(transcript.text, "Try this cafe. It is excellent.")
        self.assertEqual(len(transcript.segments), 2)

    def test_identifies_a_video_without_speech_as_optional_transcript_unavailable(self) -> None:
        """Distinguish a valid silent video from a failed TikTok provider request."""
        with patch.dict(os.environ, {"SCRAPEBADGER_API_KEY": "test-key"}), patch(
            "app.services.tiktok.urlopen", return_value=self.mock_response({"voice_to_text": None, "subtitles": []})
        ):
            with self.assertRaises(TikTokTranscriptUnavailable):
                fetch_tiktok_transcript("https://www.tiktok.com/@jetsetter/video/123")

    def test_requires_a_full_tiktok_video_url(self) -> None:
        """Reject unsupported hosts and short links that do not contain a video identifier."""
        with self.assertRaises(TikTokMetadataError):
            validate_tiktok_url("https://example.com/not-a-video")
        with self.assertRaises(TikTokMetadataError):
            extract_video_id("https://vm.tiktok.com/short-link")

    def test_expands_share_links_before_video_id_extraction(self) -> None:
        """Follow a TikTok-only share-link redirect and return its canonical video URL."""
        response = MagicMock()
        response.geturl.return_value = "https://www.tiktok.com/@jetsetter/video/123"
        context = MagicMock()
        context.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = context
        with patch("app.services.tiktok.build_opener", return_value=opener):
            resolved = resolve_tiktok_url("https://vt.tiktok.com/ZSXmaGYcE/")

        self.assertEqual(resolved, "https://www.tiktok.com/@jetsetter/video/123")
