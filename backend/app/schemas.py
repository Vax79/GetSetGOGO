from datetime import date, datetime, time

from pydantic import BaseModel, Field


class TripCreate(BaseModel):
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


class ManualActivityCreate(BaseModel):
    """Payload for saving an activity entered without a social-media link."""

    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=255)
    scheduled_date: date | None = None
    scheduled_time: time | None = None


class ActivityUpdate(BaseModel):
    """Editable activity fields, including its optional itinerary placement."""

    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=255)
    scheduled: bool
    scheduled_date: date | None = None
    scheduled_time: time | None = None


class ActivityRead(BaseModel):
    """Activity response enriched with its itinerary-specific child data."""

    id: int
    trip_id: int
    name: str
    category: str
    address: str | None
    scheduled: bool
    scheduled_date: date | None
    scheduled_time: time | None
    sort_order: int | None
    created_at: datetime


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
