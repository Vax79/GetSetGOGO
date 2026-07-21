from collections.abc import Generator
from datetime import date
import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..categories import ACTIVITY_CATEGORIES, canonical_category
from ..auth import active_user, require_trip_access
from ..database import SessionLocal
from ..models import Activity, ScheduledActivity, Trip, User
from ..schemas import ActivityRead, ActivityUpdate, ManualActivityCreate, PlaceSearchResult, ReorderActivities, RouteSegmentRead
from ..services.collaboration import clean_display_name, ensure_trip_member, ensure_user_membership
from ..services.places import GeocodingError, search_places
from ..services.routes import RoutesError, compute_itinerary_route

router = APIRouter(tags=["activities"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for an activity request and close it afterward."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def normalize_name(name: str) -> str:
    """Normalize an activity name for the duplicate-detection rule used in later steps."""
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def require_trip(trip_id: int, database: Session) -> Trip:
    """Return a trip or raise a consistent 404 response when it does not exist."""
    trip = database.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    require_trip_access(trip, database)
    return trip


def require_activity(activity_id: int, database: Session) -> Activity:
    """Return an activity or raise a consistent 404 response when it does not exist."""
    activity = database.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found.")
    trip = database.get(Trip, activity.trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    require_trip_access(trip, database)
    return activity


def require_unique_activity_name(trip_id: int, name: str, database: Session, ignored_activity_id: int | None = None) -> None:
    """Reject a normalized activity-name duplicate within one trip before it can be persisted."""
    query = database.query(Activity).filter_by(trip_id=trip_id, normalized_name=normalize_name(name))
    if ignored_activity_id is not None:
        query = query.filter(Activity.id != ignored_activity_id)
    duplicate = query.first()
    if duplicate:
        raise HTTPException(status_code=409, detail=f"An activity named '{duplicate.name}' already exists for this trip.")


def validate_scheduled_date(scheduled_date: date, trip: Trip) -> None:
    """Ensure manually scheduled activities fall within their trip's date range."""
    if not trip.start_date <= scheduled_date <= trip.end_date:
        raise HTTPException(
            status_code=422,
            detail="Scheduled date must fall within the trip dates.",
        )


def category_values(category_text: str) -> list[str]:
    """Turn a comma-separated manual category entry into a small, unique category list."""
    categories: list[str] = []
    seen: set[str] = set()
    for item in category_text.split(","):
        category = canonical_category(item)
        if not category:
            valid_categories = ", ".join(ACTIVITY_CATEGORIES)
            raise HTTPException(status_code=422, detail=f"Choose categories from: {valid_categories}.")
        key = category.casefold()
        if key in seen:
            continue
        seen.add(key)
        categories.append(category[:80])
    if not categories:
        raise HTTPException(status_code=422, detail="Add at least one category.")
    return categories[:5]


def stored_categories(activity: Activity) -> list[str]:
    """Read modern category lists while retaining a single legacy category as a fallback."""
    try:
        values = json.loads(activity.categories) if activity.categories else None
    except json.JSONDecodeError:
        values = None
    if isinstance(values, list):
        categories = [str(value).strip() for value in values if str(value).strip()]
        if categories:
            return categories
    return [activity.category] if activity.category else []


def serialize_activity(activity: Activity, scheduled: ScheduledActivity | None, submitted_by: str | None = None) -> dict[str, object]:
    """Flatten an activity and its optional scheduled child into the API response shape."""
    return {
        "id": activity.id,
        "trip_id": activity.trip_id,
        "name": activity.name,
        "category": activity.category,
        "categories": stored_categories(activity),
        "address": activity.address,
        "latitude": activity.latitude,
        "longitude": activity.longitude,
        "operating_hours": activity.operating_hours,
        "estimated_cost": activity.estimated_cost,
        "source_url": activity.source_url,
        "submitted_by": submitted_by,
        "scheduled": scheduled is not None,
        "scheduled_date": scheduled.scheduled_date if scheduled else None,
        "scheduled_time": scheduled.scheduled_time if scheduled else None,
        "sort_order": scheduled.sort_order if scheduled else None,
        "enrichment_data": json.loads(activity.enrichment_data) if activity.enrichment_data else None,
        "created_at": activity.created_at,
    }


def scheduled_record(activity_id: int, database: Session) -> ScheduledActivity | None:
    """Look up the one itinerary-placement child associated with an activity."""
    return database.query(ScheduledActivity).filter_by(activity_id=activity_id).one_or_none()


def next_sort_order(scheduled_date: date, database: Session) -> int:
    """Calculate the next append position for a particular itinerary day."""
    largest_order = (
        database.query(func.max(ScheduledActivity.sort_order))
        .filter(ScheduledActivity.scheduled_date == scheduled_date)
        .scalar()
    )
    return (largest_order or 0) + 1


def clear_day_route_segments(trip_id: int, scheduled_date: date, database: Session) -> None:
    """Invalidate cached route legs whenever a day's itinerary sequence changes."""
    records = (
        database.query(ScheduledActivity)
        .join(Activity, Activity.id == ScheduledActivity.activity_id)
        .filter(Activity.trip_id == trip_id, ScheduledActivity.scheduled_date == scheduled_date)
        .all()
    )
    for record in records:
        record.route_from_activity_id = None
        record.route_polyline = None
        record.route_distance_meters = None
        record.route_duration_seconds = None


def route_segment_read(record: ScheduledActivity) -> RouteSegmentRead:
    """Serialize one cached itinerary leg for both the map and timeline display."""
    return RouteSegmentRead(
        from_activity_id=record.route_from_activity_id,
        to_activity_id=record.activity_id,
        encoded_polyline=record.route_polyline,
        distance_meters=record.route_distance_meters,
        duration_seconds=record.route_duration_seconds,
    )


def route_cache_is_current(records: list[tuple[Activity, ScheduledActivity]]) -> bool:
    """Check that every later stop stores the route from its current predecessor."""
    return all(
        schedule.route_from_activity_id == previous_activity.id
        and bool(schedule.route_polyline)
        and schedule.route_duration_seconds is not None
        for (previous_activity, _), (_, schedule) in zip(records, records[1:])
    )


def day_route_segments(trip_id: int, scheduled_date: date, database: Session) -> list[RouteSegmentRead]:
    """Return cached day legs, calculating and persisting them in one call when needed."""
    records = (
        database.query(Activity, ScheduledActivity)
        .join(ScheduledActivity, ScheduledActivity.activity_id == Activity.id)
        .filter(Activity.trip_id == trip_id, ScheduledActivity.scheduled_date == scheduled_date)
        .order_by(ScheduledActivity.sort_order)
        .all()
    )
    if len(records) < 2 or not all(activity.latitude and activity.longitude for activity, _ in records):
        return []
    if not route_cache_is_current(records):
        try:
            routes = compute_itinerary_route([(activity.latitude, activity.longitude) for activity, _ in records])
        except RoutesError:
            return []
        for (previous_activity, _), (_, schedule), route in zip(records, records[1:], routes):
            schedule.route_from_activity_id = previous_activity.id
            schedule.route_polyline = route.encoded_polyline
            schedule.route_distance_meters = route.distance_meters
            schedule.route_duration_seconds = route.duration_seconds
        database.commit()
    return [route_segment_read(schedule) for _, schedule in records[1:]]


@router.get("/api/trips/{trip_id}/activities", response_model=list[ActivityRead])
def list_activities(
    trip_id: int,
    scheduled: bool | None = None,
    category: str | None = None,
    database: Session = Depends(get_db),
) -> list[dict[str, object]]:
    """List a trip's itinerary or pool, optionally filtered by placement and category."""
    require_trip(trip_id, database)
    query = database.query(Activity, ScheduledActivity, User.name).outerjoin(
        ScheduledActivity, ScheduledActivity.activity_id == Activity.id
    ).outerjoin(User, User.id == Activity.submitted_by_id).filter(Activity.trip_id == trip_id)
    if scheduled is True:
        query = query.filter(ScheduledActivity.id.is_not(None))
    elif scheduled is False:
        query = query.filter(ScheduledActivity.id.is_(None))
    if category:
        query = query.filter(Activity.category == category)

    records = query.order_by(
        ScheduledActivity.scheduled_date.asc(),
        ScheduledActivity.sort_order.asc(),
        Activity.created_at.desc(),
    ).all()
    return [serialize_activity(activity, placement, submitted_by) for activity, placement, submitted_by in records]


@router.get("/api/trips/{trip_id}/place-search", response_model=list[PlaceSearchResult])
def search_manual_activity_places(
    trip_id: int,
    query: str,
    database: Session = Depends(get_db),
) -> list[PlaceSearchResult]:
    """Search Google Places for a manual address and return selectable geocoded matches."""
    trip = require_trip(trip_id, database)
    try:
        return [PlaceSearchResult(**place.__dict__) for place in search_places(query, ", ".join(part for part in (trip.destination_city, trip.destination_region) if part))]
    except GeocodingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/api/trips/{trip_id}/activities",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_activity(
    trip_id: int,
    payload: ManualActivityCreate,
    database: Session = Depends(get_db),
) -> dict[str, object]:
    """Create a manual activity and optionally place it on a selected itinerary date."""
    trip = require_trip(trip_id, database)
    require_unique_activity_name(trip_id, payload.name, database)
    if payload.scheduled_date:
        validate_scheduled_date(payload.scheduled_date, trip)

    submitted_by = clean_display_name(payload.submitted_by_name)
    contributor = active_user()
    if contributor:
        ensure_user_membership(trip, contributor, database)
    elif submitted_by:
        contributor = ensure_trip_member(trip, submitted_by, database)
    categories = category_values(payload.category)
    activity = Activity(
        trip_id=trip_id,
        name=payload.name.strip(),
        normalized_name=normalize_name(payload.name),
        category=categories[0],
        categories=json.dumps(categories),
        address=payload.address.strip(),
        estimated_cost=payload.estimated_cost.strip() if payload.estimated_cost else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        operating_hours=payload.operating_hours,
        submitted_by_id=contributor.id if contributor else None,
        scheduled=payload.scheduled_date is not None,
    )
    database.add(activity)
    database.flush()

    placement = None
    if payload.scheduled_date:
        placement = ScheduledActivity(
            activity_id=activity.id,
            scheduled_date=payload.scheduled_date,
            scheduled_time=payload.scheduled_time,
            sort_order=next_sort_order(payload.scheduled_date, database),
        )
        database.add(placement)
        clear_day_route_segments(trip_id, payload.scheduled_date, database)

    database.commit()
    database.refresh(activity)
    if placement:
        database.refresh(placement)
    return serialize_activity(activity, placement, contributor.name if contributor else None)


@router.patch("/api/activities/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    database: Session = Depends(get_db),
) -> dict[str, object]:
    """Edit a manual activity and create, update, or remove its itinerary placement."""
    activity = require_activity(activity_id, database)
    trip = require_trip(activity.trip_id, database)
    require_unique_activity_name(activity.trip_id, payload.name, database, activity_id)
    activity.name = payload.name.strip()
    activity.normalized_name = normalize_name(payload.name)
    categories = category_values(payload.category)
    activity.category = categories[0]
    activity.categories = json.dumps(categories)
    activity.address = payload.address.strip()
    activity.estimated_cost = payload.estimated_cost.strip() if payload.estimated_cost else None
    activity.latitude = payload.latitude
    activity.longitude = payload.longitude
    activity.operating_hours = payload.operating_hours
    placement = scheduled_record(activity_id, database)
    previous_date = placement.scheduled_date if placement else None

    if payload.scheduled:
        if not payload.scheduled_date:
            raise HTTPException(status_code=422, detail="Choose a date before scheduling an activity.")
        validate_scheduled_date(payload.scheduled_date, trip)
        if placement:
            placement.scheduled_date = payload.scheduled_date
            placement.scheduled_time = payload.scheduled_time
        else:
            placement = ScheduledActivity(
                activity_id=activity.id,
                scheduled_date=payload.scheduled_date,
                scheduled_time=payload.scheduled_time,
                sort_order=next_sort_order(payload.scheduled_date, database),
            )
            database.add(placement)
        activity.scheduled = True
    else:
        if placement:
            database.delete(placement)
            placement = None
        activity.scheduled = False

    if previous_date:
        clear_day_route_segments(activity.trip_id, previous_date, database)
    if placement:
        clear_day_route_segments(activity.trip_id, placement.scheduled_date, database)

    database.commit()
    database.refresh(activity)
    if placement:
        database.refresh(placement)
    contributor = database.get(User, activity.submitted_by_id) if activity.submitted_by_id else None
    return serialize_activity(activity, placement, contributor.name if contributor else None)


@router.delete("/api/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int, database: Session = Depends(get_db)) -> None:
    """Delete an activity and any itinerary placement that belongs to it."""
    activity = require_activity(activity_id, database)
    placement = scheduled_record(activity.id, database)
    if placement:
        clear_day_route_segments(activity.trip_id, placement.scheduled_date, database)
        database.delete(placement)
    database.delete(activity)
    database.commit()


@router.put("/api/trips/{trip_id}/itinerary/{scheduled_date}/order", status_code=status.HTTP_204_NO_CONTENT)
def reorder_day(
    trip_id: int,
    scheduled_date: date,
    payload: ReorderActivities,
    database: Session = Depends(get_db),
) -> None:
    """Persist a drag-and-drop order for every scheduled activity on one day."""
    require_trip(trip_id, database)
    records = (
        database.query(ScheduledActivity)
        .join(Activity, Activity.id == ScheduledActivity.activity_id)
        .filter(Activity.trip_id == trip_id, ScheduledActivity.scheduled_date == scheduled_date)
        .all()
    )
    found_ids = {record.activity_id for record in records}
    if found_ids != set(payload.activity_ids) or len(found_ids) != len(payload.activity_ids):
        raise HTTPException(status_code=422, detail="Order must include each activity on this day exactly once.")

    positions = {activity_id: index + 1 for index, activity_id in enumerate(payload.activity_ids)}
    for record in records:
        record.sort_order = positions[record.activity_id]
    clear_day_route_segments(trip_id, scheduled_date, database)
    database.commit()


@router.get("/api/trips/{trip_id}/itinerary/{scheduled_date}/routes", response_model=list[RouteSegmentRead])
def list_day_route_segments(
    trip_id: int,
    scheduled_date: date,
    database: Session = Depends(get_db),
) -> list[RouteSegmentRead]:
    """Return cached route legs and compute all consecutive travel times in one call when needed."""
    require_trip(trip_id, database)
    return day_route_segments(trip_id, scheduled_date, database)
