import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

SCRAPEBADGER_BASE_URL = "https://scrapebadger.com/v1/tiktok"
TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}


class TikTokMetadataError(Exception):
    """Represent a ScrapeBadger request that cannot produce usable TikTok data."""


class TikTokTranscriptUnavailable(TikTokMetadataError):
    """Represent a valid video whose speech-to-text transcript is unavailable or empty."""


class SafeTikTokRedirectHandler(HTTPRedirectHandler):
    """Follow share-link redirects only when every target remains a TikTok-owned host."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        """Validate each redirect target before allowing urllib to request it."""
        target_url = urljoin(request.full_url, newurl)
        validate_tiktok_url(target_url)
        return super().redirect_request(request, fp, code, message, headers, target_url)


@dataclass(frozen=True)
class TikTokMetadata:
    """Store normalized video-detail metadata returned by ScrapeBadger."""

    source_url: str
    video_id: str
    caption: str
    hashtags: list[str]
    author_name: str | None
    author_url: str | None
    thumbnail_url: str | None


@dataclass(frozen=True)
class TikTokTranscript:
    """Store full speech-to-text output and optional timestamped transcript segments."""

    source_url: str
    video_id: str
    text: str
    segments: list[dict[str, object]]


def validate_tiktok_url(source_url: str) -> str:
    """Accept only an absolute TikTok URL so the server never fetches arbitrary hosts."""
    candidate = source_url.strip()
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or hostname not in TIKTOK_HOSTS or parsed.username or parsed.password:
        raise TikTokMetadataError("Enter a valid TikTok video URL.")
    return candidate


def resolve_tiktok_url(source_url: str) -> str:
    """Expand a TikTok share URL to its canonical video URL before extracting the ID."""
    valid_url = validate_tiktok_url(source_url)
    hostname = (urlparse(valid_url).hostname or "").lower()
    if hostname not in {"vm.tiktok.com", "vt.tiktok.com"}:
        return valid_url

    request = Request(valid_url, headers={"User-Agent": "JetSetGo/0.1"})
    try:
        with build_opener(SafeTikTokRedirectHandler()).open(request, timeout=15) as response:
            resolved_url = response.geturl()
    except (HTTPError, URLError, TimeoutError) as error:
        raise TikTokMetadataError("TikTok could not expand this share link.") from error

    validate_tiktok_url(resolved_url)
    if not re.search(r"/(?:video|photo)/\d+(?:/|$|[?#])", urlparse(resolved_url).path):
        raise TikTokMetadataError("TikTok share link did not resolve to a video URL.")
    return resolved_url


def extract_video_id(source_url: str) -> str:
    """Extract the numeric video ID required by ScrapeBadger's TikTok endpoints."""
    valid_url = validate_tiktok_url(source_url)
    match = re.search(r"/(?:video|photo)/(\d+)(?:/|$|[?#])", urlparse(valid_url).path)
    if not match:
        raise TikTokMetadataError("Use a full TikTok video URL containing its numeric video ID.")
    return match.group(1)


def extract_username(source_url: str) -> str | None:
    """Return an optional TikTok author handle to optimize ScrapeBadger video lookups."""
    match = re.search(r"/@([^/]+)/", urlparse(source_url).path)
    return match.group(1) if match else None


def extract_hashtags(caption: str) -> list[str]:
    """Extract unique hashtag text when a provider response does not include a tag list."""
    seen: set[str] = set()
    hashtags: list[str] = []
    for tag in re.findall(r"(?<!\w)#([\w]+)", caption, flags=re.UNICODE):
        normalized = tag.casefold()
        if normalized not in seen:
            seen.add(normalized)
            hashtags.append(tag)
    return hashtags


def get_scrapebadger_api_key() -> str:
    """Read the required server-side ScrapeBadger credential without exposing it to clients."""
    api_key = os.getenv("SCRAPEBADGER_API_KEY", "").strip()
    if not api_key:
        raise TikTokMetadataError("ScrapeBadger is not configured. Add SCRAPEBADGER_API_KEY to .env.")
    return api_key


def fetch_scrapebadger_json(path: str, params: dict[str, str] | None = None) -> dict[str, object]:
    """Call one authenticated ScrapeBadger endpoint and decode its JSON response."""
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{SCRAPEBADGER_BASE_URL}{path}{query}",
        headers={"x-api-key": get_scrapebadger_api_key(), "User-Agent": "JetSetGo/0.1"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - provider base URL is constant.
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise TikTokMetadataError("ScrapeBadger could not retrieve TikTok data for this link.") from error


def request_params(source_url: str) -> dict[str, str]:
    """Build shared region and optional author parameters for ScrapeBadger requests."""
    params = {"region": os.getenv("SCRAPEBADGER_REGION", "US").upper()}
    if username := extract_username(source_url):
        params["username"] = username
    return params


def fetch_tiktok_metadata(source_url: str) -> TikTokMetadata:
    """Retrieve full public TikTok video metadata through ScrapeBadger's detail endpoint."""
    valid_url = resolve_tiktok_url(source_url)
    video_id = extract_video_id(valid_url)
    payload = fetch_scrapebadger_json(f"/videos/{video_id}", request_params(valid_url))
    video = payload.get("video")
    if not isinstance(video, dict):
        raise TikTokMetadataError("ScrapeBadger returned no TikTok video metadata.")

    caption = str(video.get("description") or "").strip()
    if not caption:
        raise TikTokMetadataError("ScrapeBadger returned no caption for this TikTok video.")
    author = video.get("author") if isinstance(video.get("author"), dict) else {}
    tags = video.get("hashtags")
    hashtags = [str(tag) for tag in tags if str(tag).strip()] if isinstance(tags, list) else extract_hashtags(caption)
    username = str(author.get("unique_id") or "").strip()
    media = video.get("video") if isinstance(video.get("video"), dict) else {}
    return TikTokMetadata(
        source_url=str(video.get("share_url") or video.get("url") or valid_url),
        video_id=video_id,
        caption=caption,
        hashtags=hashtags,
        author_name=str(author.get("nickname") or username).strip() or None,
        author_url=f"https://www.tiktok.com/@{username}" if username else None,
        thumbnail_url=str(media.get("cover") or "").strip() or None,
    )


def normalize_segments(value: object) -> list[dict[str, object]]:
    """Normalize likely ScrapeBadger transcript segment shapes into a stable API list."""
    if not isinstance(value, list):
        return []
    return [segment for segment in value if isinstance(segment, dict)]


def transcript_text(value: object) -> str:
    """Extract transcript prose from string, object, or segment-list ScrapeBadger variants."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("transcript") or "").strip()
    if isinstance(value, list):
        return " ".join(
            str(segment.get("text") or "").strip()
            for segment in value
            if isinstance(segment, dict)
        ).strip()
    return ""


def fetch_tiktok_transcript(source_url: str) -> TikTokTranscript:
    """Retrieve the complete ASR speech-to-text transcript through ScrapeBadger."""
    valid_url = resolve_tiktok_url(source_url)
    video_id = extract_video_id(valid_url)
    payload = fetch_scrapebadger_json(f"/videos/{video_id}/transcript", request_params(valid_url))
    transcript = payload.get("transcript")
    voice_to_text = payload.get("voice_to_text")
    transcript_data = transcript if isinstance(transcript, dict) else {}
    voice_data = voice_to_text if isinstance(voice_to_text, dict) else {}
    segments = normalize_segments(
        payload.get("segments")
        or transcript_data.get("segments")
        or voice_data.get("segments")
        or voice_to_text
    )
    text = (
        transcript_text(payload.get("text"))
        or transcript_text(payload.get("transcript_text"))
        or transcript_text(voice_to_text)
        or transcript_text(transcript)
    )
    if not text and segments:
        text = " ".join(str(segment.get("text") or "").strip() for segment in segments).strip()
    if not text:
        raise TikTokTranscriptUnavailable("ScrapeBadger could not detect speech in this TikTok video.")
    return TikTokTranscript(source_url=valid_url, video_id=video_id, text=text, segments=segments)
