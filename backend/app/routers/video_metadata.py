from collections.abc import Generator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..routers.activities import require_trip
from ..schemas import TikTokMetadataRequest, VideoMetadataRead, VideoTranscriptRead
from ..services.tiktok import TikTokMetadataError, fetch_tiktok_metadata, fetch_tiktok_transcript

router = APIRouter(prefix="/api/trips/{trip_id}/video-metadata", tags=["video metadata"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session so metadata requests can validate their trip."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


@router.post("", response_model=VideoMetadataRead)
def retrieve_tiktok_metadata(
    trip_id: int,
    payload: TikTokMetadataRequest,
    database: Session = Depends(get_db),
) -> VideoMetadataRead:
    """Fetch a TikTok preview for an existing trip without saving an activity."""
    require_trip(trip_id, database)
    try:
        metadata = fetch_tiktok_metadata(payload.source_url)
    except TikTokMetadataError as error:
        return VideoMetadataRead(source_url=payload.source_url, detected=False, message=str(error))
    return VideoMetadataRead(
        source_url=metadata.source_url,
        detected=True,
        caption=metadata.caption,
        hashtags=metadata.hashtags,
        author_name=metadata.author_name,
        author_url=metadata.author_url,
        thumbnail_url=metadata.thumbnail_url,
        message="TikTok metadata detected through ScrapeBadger.",
    )


@router.post("/transcript", response_model=VideoTranscriptRead)
def retrieve_tiktok_transcript(
    trip_id: int,
    payload: TikTokMetadataRequest,
    database: Session = Depends(get_db),
) -> VideoTranscriptRead:
    """Fetch a full TikTok speech-to-text transcript without saving an activity."""
    require_trip(trip_id, database)
    try:
        transcript = fetch_tiktok_transcript(payload.source_url)
    except TikTokMetadataError as error:
        return VideoTranscriptRead(source_url=payload.source_url, detected=False, message=str(error))
    return VideoTranscriptRead(
        source_url=transcript.source_url,
        video_id=transcript.video_id,
        detected=True,
        text=transcript.text,
        segments=transcript.segments,
        message="TikTok speech-to-text transcript detected through ScrapeBadger.",
    )
