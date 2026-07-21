from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    destination_city: str | None = Field(default=None, max_length=120)
    destination_region: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date


class TripUpdate(BaseModel):
    """Editable trip-level information shown in the trip settings dialog."""

    name: str = Field(min_length=1, max_length=160)
    destination_city: str | None = Field(default=None, max_length=120)
    destination_region: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date


class TripRead(BaseModel):
    id: int
    name: str
    destination_city: str | None
    destination_region: str | None
    start_date: date
    end_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class DisplayNameRequest(BaseModel):
    """Identify a lightweight collaborator by their display name."""

    display_name: str = Field(min_length=1, max_length=80)


class UserRead(BaseModel):
    """A collaborator profile linked to an authenticated email when available."""

    id: int
    name: str
    email: str | None
    username: str | None

    model_config = {"from_attributes": True}


class PasswordRegister(BaseModel):
    """Create or claim an app account using a unique username and password."""

    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class PasswordLogin(BaseModel):
    """Authenticate an existing account without exposing an email address."""

    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class AuthSessionRead(BaseModel):
    """Return one opaque bearer token and the associated safe profile fields."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ShareTripRead(BaseModel):
    """A share code and route used to invite someone into a trip."""

    share_code: str


class JoinTripRequest(DisplayNameRequest):
    """Join a shared trip using its short code and a display name."""

    share_code: str = Field(min_length=4, max_length=32)


class JoinedTripRead(BaseModel):
    """The shared trip and collaborator identity established by a join request."""

    trip: TripRead
    user: UserRead


class VoteRequest(DisplayNameRequest):
    """A visual preference vote that never alters approval or scheduling."""

    vote_value: Literal[-1, 1]


class VoteCandidateRead(BaseModel):
    """An unvoted activity presented in the swipe voting deck."""

    id: int
    name: str
    category: str
    address: str | None
    estimated_cost: str | None
    scheduled: bool
    submitted_by: str | None
    vote_score: int


class ManualActivityCreate(BaseModel):
    """Payload for saving an activity entered without a social-media link."""

    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=255)
    estimated_cost: str | None = Field(default=None, max_length=80)
    latitude: str | None = Field(default=None, max_length=32)
    longitude: str | None = Field(default=None, max_length=32)
    operating_hours: str | None = None
    submitted_by_name: str | None = Field(default=None, max_length=80)
    scheduled_date: date | None = None
    scheduled_time: time | None = None


class ActivityUpdate(BaseModel):
    """Editable activity fields, including its optional itinerary placement."""

    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=255)
    estimated_cost: str | None = Field(default=None, max_length=80)
    latitude: str | None = Field(default=None, max_length=32)
    longitude: str | None = Field(default=None, max_length=32)
    operating_hours: str | None = None
    scheduled: bool
    scheduled_date: date | None = None
    scheduled_time: time | None = None


class ActivityRead(BaseModel):
    """Activity response enriched with its itinerary-specific child data."""

    id: int
    trip_id: int
    name: str
    category: str
    categories: list[str]
    address: str | None
    latitude: str | None
    longitude: str | None
    operating_hours: str | None
    estimated_cost: str | None
    source_url: str | None
    submitted_by: str | None
    scheduled: bool
    scheduled_date: date | None
    scheduled_time: time | None
    sort_order: int | None
    enrichment_data: dict[str, object] | None
    created_at: datetime


class PlaceSearchResult(BaseModel):
    """A selectable Google Places match for a manual activity entry."""

    name: str
    address: str | None
    latitude: str | None
    longitude: str | None
    operating_hours: str | None


class ExtractActivitiesRequest(BaseModel):
    """Previewed TikTok context used to derive activity and POI candidates with Gemini."""

    source_url: str = Field(min_length=1, max_length=2048)
    caption: str | None = Field(default=None, min_length=1, max_length=10_000)
    transcript: str | None = None
    include_transcript: bool = False


class ExtractedActivityRead(BaseModel):
    """A non-persisted activity candidate returned for explicit approval or rejection."""

    activity_name: str
    categories: list[str]
    poi_name: str
    poi_address: str | None
    estimated_cost: str | None
    source_url: str
    geocoded: bool
    geocoding_message: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    operating_hours: str | None = None


class ExtractActivitiesRead(BaseModel):
    """All candidates found in a single social-video extraction run."""

    activities: list[ExtractedActivityRead]
    message: str


class SaveExtractedActivityRequest(BaseModel):
    """An approved Gemini candidate that should be saved as an activity."""

    activity_name: str = Field(min_length=1, max_length=180)
    categories: list[str] = Field(min_length=1, max_length=5)
    poi_name: str = Field(min_length=1, max_length=180)
    poi_address: str | None = Field(default=None, max_length=255)
    estimated_cost: str | None = Field(default=None, max_length=80)
    source_url: str = Field(min_length=1, max_length=2048)
    latitude: str | None = Field(default=None, max_length=32)
    longitude: str | None = Field(default=None, max_length=32)
    operating_hours: str | None = None
    submitted_by_name: str | None = Field(default=None, max_length=80)


class EnrichmentRead(ActivityRead):
    """An activity after Gemini enrichment has been saved to enrichment_data."""


class PlacementRead(BaseModel):
    """Outcome of travel-distance placement performed immediately after approval."""

    scheduled: bool
    message: str
    nearest_activity_name: str | None = None
    distance_meters: int | None = None
    travel_duration_seconds: int | None = None


class ApprovedActivityRead(ActivityRead):
    """An approved activity together with its automatic itinerary-placement result."""

    placement: PlacementRead


class RouteSegmentRead(BaseModel):
    """A saved placement-time route segment used to connect itinerary pins on the map."""

    from_activity_id: int
    to_activity_id: int
    encoded_polyline: str
    distance_meters: int | None = None
    duration_seconds: int | None = None


class ReorderActivities(BaseModel):
    """Ordered activity identifiers for one itinerary day."""

    activity_ids: list[int] = Field(min_length=1)


class TikTokMetadataRequest(BaseModel):
    """TikTok video link submitted for metadata retrieval."""

    source_url: str = Field(min_length=1, max_length=2048)


class VideoMetadataRead(BaseModel):
    """Non-persisted TikTok metadata preview shown before Step 5 extraction."""

    source_url: str
    detected: bool
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    author_name: str | None = None
    author_url: str | None = None
    thumbnail_url: str | None = None
    message: str


class VideoTranscriptRead(BaseModel):
    """Full non-persisted TikTok speech-to-text transcript and timestamped segments."""

    source_url: str
    video_id: str | None = None
    detected: bool
    text: str | None = None
    segments: list[dict[str, object]] = Field(default_factory=list)
    message: str
