"""Routes for Gemini activity extraction and stored POI enrichment."""

import json
from collections.abc import Generator
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..auth import active_user
from ..models import Activity, ScheduledActivity, Trip, User
from ..schemas import (
    ActivityRead,
    ApprovedActivityRead,
    EnrichmentRead,
    ExtractActivitiesRead,
    ExtractActivitiesRequest,
    ExtractedActivityRead,
    PlacementRead,
    SaveExtractedActivityRequest,
)
from ..services.gemini import GeminiError, enrich_activity_data, extract_activities
from ..services.places import GeocodingError, geocode_place
from ..services.routes import RoutesError, compute_route, route_matrix
from ..services.tiktok import TikTokMetadataError, TikTokTranscriptUnavailable, fetch_tiktok_metadata, fetch_tiktok_transcript, validate_tiktok_url
from .activities import category_values, normalize_name, require_activity, require_trip, require_unique_activity_name, scheduled_record, serialize_activity
from ..services.collaboration import clean_display_name, ensure_trip_member, ensure_user_membership

router = APIRouter(tags=["enrichment"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for extraction and enrichment requests."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def trip_destination(trip: Trip) -> str:
    """Format the known trip destination as concise context for Gemini prompts."""
    return ", ".join(part for part in (trip.destination_city, trip.destination_region) if part)


def unique_new_candidates(candidates: list[object], existing_names: set[str]) -> list[object]:
    """Discard normalized-name duplicates from stored activities and this extraction batch."""
    seen_names: set[str] = set()
    unique: list[object] = []
    for candidate in candidates:
        activity_name = getattr(candidate, "activity_name", "")
        normalized = normalize_name(activity_name)
        if not normalized or normalized in existing_names or normalized in seen_names:
            continue
        seen_names.add(normalized)
        unique.append(candidate)
    return unique


def placement_time(existing_time: time | None) -> time | None:
    """Place a nearest-neighbor activity 90 minutes later when its time is known."""
    if not existing_time:
        return None
    return (datetime.combine(datetime.today(), existing_time) + timedelta(minutes=90)).time()


def save_route_segment(
    placement: ScheduledActivity,
    from_activity: Activity,
    to_activity: Activity,
) -> None:
    """Persist a placement-time Google Routes polyline for a consecutive itinerary pair."""
    if not all((from_activity.latitude, from_activity.longitude, to_activity.latitude, to_activity.longitude)):
        placement.route_from_activity_id = None
        placement.route_polyline = None
        placement.route_distance_meters = None
        placement.route_duration_seconds = None
        return
    try:
        route = compute_route(
            (from_activity.latitude, from_activity.longitude),
            (to_activity.latitude, to_activity.longitude),
        )
    except RoutesError:
        placement.route_from_activity_id = None
        placement.route_polyline = None
        placement.route_distance_meters = None
        placement.route_duration_seconds = None
        return
    placement.route_from_activity_id = from_activity.id
    placement.route_polyline = route.encoded_polyline
    placement.route_distance_meters = route.distance_meters
    placement.route_duration_seconds = route.duration_seconds


def place_approved_activity(activity: Activity, trip: Trip, database: Session) -> PlacementRead:
    """Place an approved activity as the first event or after its nearest routed neighbor."""
    records = (
        database.query(Activity, ScheduledActivity)
        .join(ScheduledActivity, ScheduledActivity.activity_id == Activity.id)
        .filter(Activity.trip_id == trip.id)
        .order_by(ScheduledActivity.scheduled_date, ScheduledActivity.sort_order)
        .all()
    )
    if not records:
        placement = ScheduledActivity(activity_id=activity.id, scheduled_date=trip.start_date, scheduled_time=time(12), sort_order=1)
        database.add(placement)
        activity.scheduled = True
        return PlacementRead(scheduled=True, message="Added as the first itinerary event on the trip start date.")
    if not activity.latitude or not activity.longitude:
        return PlacementRead(scheduled=False, message="Approved and saved to the activity pool because its location has no coordinates.")

    geo_records = [(other_activity, schedule) for other_activity, schedule in records if other_activity.latitude and other_activity.longitude]
    if not geo_records:
        return PlacementRead(scheduled=False, message="Approved and saved to the activity pool because scheduled events have no coordinates to compare.")
    try:
        metrics = route_matrix(
            (activity.latitude, activity.longitude),
            [(other.latitude, other.longitude) for other, _ in geo_records],
        )
    except RoutesError as error:
        return PlacementRead(scheduled=False, message=f"Approved and saved to the activity pool: {error}")
    ranked = [(metric.distance_meters, index, metric) for index, metric in metrics.items() if index < len(geo_records)]
    if not ranked:
        return PlacementRead(scheduled=False, message="Approved and saved to the activity pool because no drivable route was found.")
    _, nearest_index, metric = min(ranked)
    nearest_activity, nearest_schedule = geo_records[nearest_index]
    later_records = database.query(Activity, ScheduledActivity).join(ScheduledActivity, ScheduledActivity.activity_id == Activity.id).filter(
        Activity.trip_id == trip.id,
        ScheduledActivity.scheduled_date == nearest_schedule.scheduled_date,
        ScheduledActivity.sort_order > nearest_schedule.sort_order,
    ).order_by(ScheduledActivity.sort_order).all()
    next_activity, next_schedule = later_records[0] if later_records else (None, None)
    for _, later_schedule in later_records:
        later_schedule.sort_order += 1
    placement = ScheduledActivity(
        activity_id=activity.id,
        scheduled_date=nearest_schedule.scheduled_date,
        scheduled_time=placement_time(nearest_schedule.scheduled_time),
        sort_order=nearest_schedule.sort_order + 1,
    )
    database.add(placement)
    save_route_segment(placement, nearest_activity, activity)
    if next_activity and next_schedule:
        save_route_segment(next_schedule, activity, next_activity)
    activity.scheduled = True
    return PlacementRead(
        scheduled=True,
        message=f"Placed after the nearest itinerary activity, {nearest_activity.name}.",
        nearest_activity_name=nearest_activity.name,
        distance_meters=metric.distance_meters,
        travel_duration_seconds=metric.duration_seconds,
    )


@router.post("/api/trips/{trip_id}/activity-extractions", response_model=ExtractActivitiesRead)
def extract_tiktok_activities(
    trip_id: int,
    payload: ExtractActivitiesRequest,
    database: Session = Depends(get_db),
) -> ExtractActivitiesRead:
    """Use previewed TikTok context and Gemini to return non-persisted activity/POI candidates."""
    trip = require_trip(trip_id, database)
    try:
        source_url = validate_tiktok_url(payload.source_url)
    except TikTokMetadataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    caption = payload.caption.strip() if payload.caption else None
    canonical_source_url = source_url
    if not caption:
        try:
            metadata = fetch_tiktok_metadata(source_url)
        except TikTokMetadataError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        caption = metadata.caption
        canonical_source_url = metadata.source_url
    transcript = payload.transcript.strip() if payload.transcript else None
    if not transcript and payload.include_transcript:
        try:
            transcript = fetch_tiktok_transcript(source_url).text
        except TikTokTranscriptUnavailable:
            transcript = None
        except TikTokMetadataError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        candidates = extract_activities(trip_destination(trip), caption, transcript)
    except GeminiError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    existing_names = {activity.normalized_name for activity in database.query(Activity).filter_by(trip_id=trip_id)}
    destination = trip_destination(trip)
    response_activities: list[ExtractedActivityRead] = []
    for candidate in unique_new_candidates(candidates, existing_names):
        try:
            place = geocode_place(candidate.poi_name, destination)
            response_activities.append(
                ExtractedActivityRead(
                    activity_name=candidate.activity_name,
                    categories=candidate.categories,
                    poi_name=place.name,
                    poi_address=place.address,
                    estimated_cost=candidate.estimated_cost,
                    source_url=canonical_source_url,
                    geocoded=True,
                    latitude=place.latitude,
                    longitude=place.longitude,
                    operating_hours=place.operating_hours,
                )
            )
        except GeocodingError as error:
            response_activities.append(
                ExtractedActivityRead(
                    activity_name=candidate.activity_name,
                    categories=candidate.categories,
                    poi_name=candidate.poi_name,
                    poi_address=candidate.poi_address,
                    estimated_cost=candidate.estimated_cost,
                    source_url=canonical_source_url,
                    geocoded=False,
                    geocoding_message=str(error),
                )
            )
    return ExtractActivitiesRead(
        activities=response_activities,
        message="Gemini extracted new activity candidates and Google Places attempted geocoding. Review before approval.",
    )


@router.post(
    "/api/trips/{trip_id}/activity-extractions/approve",
    response_model=ApprovedActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def approve_extracted_activity(
    trip_id: int,
    payload: SaveExtractedActivityRequest,
    database: Session = Depends(get_db),
) -> ApprovedActivityRead:
    """Approve, persist, and attempt distance-based placement for one reviewed candidate."""
    trip = require_trip(trip_id, database)
    normalized = normalize_name(payload.activity_name)
    require_unique_activity_name(trip_id, payload.activity_name, database)

    submitted_by = clean_display_name(payload.submitted_by_name)
    contributor = active_user()
    if contributor:
        ensure_user_membership(trip, contributor, database)
    elif submitted_by:
        contributor = ensure_trip_member(trip, submitted_by, database)
    categories = category_values(",".join(payload.categories))
    activity = Activity(
        trip_id=trip_id,
        name=payload.activity_name.strip(),
        normalized_name=normalized,
        category=categories[0],
        categories=json.dumps(categories),
        address=(payload.poi_address or payload.poi_name).strip(),
        estimated_cost=payload.estimated_cost.strip() if payload.estimated_cost else None,
        source_url=payload.source_url.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        operating_hours=payload.operating_hours,
        submitted_by_id=contributor.id if contributor else None,
        scheduled=False,
    )
    database.add(activity)
    database.flush()
    placement = place_approved_activity(activity, trip, database)
    try:
        activity.enrichment_data = json.dumps(enrich_activity_data(activity.name, activity.address, trip_destination(trip)))
    except GeminiError:
        # Enrichment is helpful card context, but approval and placement must remain available without it.
        pass
    database.commit()
    database.refresh(activity)
    return ApprovedActivityRead(**serialize_activity(activity, scheduled_record(activity.id, database), contributor.name if contributor else None), placement=placement)


@router.post("/api/activities/{activity_id}/enrich", response_model=EnrichmentRead)
def enrich_activity(activity_id: int, database: Session = Depends(get_db)) -> EnrichmentRead:
    """Populate and persist the three requested enrichment sections in an activity's enrichment_data."""
    activity = require_activity(activity_id, database)
    trip = require_trip(activity.trip_id, database)
    try:
        sections = enrich_activity_data(activity.name, activity.address, trip_destination(trip))
    except GeminiError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    activity.enrichment_data = json.dumps(sections)
    database.commit()
    database.refresh(activity)
    contributor = database.get(User, activity.submitted_by_id) if activity.submitted_by_id else None
    return EnrichmentRead(**serialize_activity(activity, scheduled_record(activity.id, database), contributor.name if contributor else None))
