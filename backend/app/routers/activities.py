from collections.abc import Generator
from datetime import date
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Activity, ScheduledActivity, Trip
from ..schemas import ActivityRead, ActivityUpdate, ManualActivityCreate, ReorderActivities

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
    return trip


def require_activity(activity_id: int, database: Session) -> Activity:
    """Return an activity or raise a consistent 404 response when it does not exist."""
    activity = database.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found.")
    return activity


def validate_scheduled_date(scheduled_date: date, trip: Trip) -> None:
    """Ensure manually scheduled activities fall within their trip's date range."""
    if not trip.start_date <= scheduled_date <= trip.end_date:
        raise HTTPException(
            status_code=422,
            detail="Scheduled date must fall within the trip dates.",
        )


def serialize_activity(activity: Activity, scheduled: ScheduledActivity | None) -> dict[str, object]:
    """Flatten an activity and its optional scheduled child into the API response shape."""
    return {
        "id": activity.id,
        "trip_id": activity.trip_id,
        "name": activity.name,
        "category": activity.category,
        "address": activity.address,
        "scheduled": scheduled is not None,
        "scheduled_date": scheduled.scheduled_date if scheduled else None,
        "scheduled_time": scheduled.scheduled_time if scheduled else None,
        "sort_order": scheduled.sort_order if scheduled else None,
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


@router.get("/api/trips/{trip_id}/activities", response_model=list[ActivityRead])
def list_activities(
    trip_id: int,
    scheduled: bool | None = None,
    category: str | None = None,
    database: Session = Depends(get_db),
) -> list[dict[str, object]]:
    """List a trip's itinerary or pool, optionally filtered by placement and category."""
    require_trip(trip_id, database)
    query = database.query(Activity, ScheduledActivity).outerjoin(
        ScheduledActivity, ScheduledActivity.activity_id == Activity.id
    ).filter(Activity.trip_id == trip_id)
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
    return [serialize_activity(activity, placement) for activity, placement in records]


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
    if payload.scheduled_date:
        validate_scheduled_date(payload.scheduled_date, trip)

    activity = Activity(
        trip_id=trip_id,
        name=payload.name.strip(),
        normalized_name=normalize_name(payload.name),
        category=payload.category.strip(),
        address=payload.address.strip(),
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

    database.commit()
    database.refresh(activity)
    if placement:
        database.refresh(placement)
    return serialize_activity(activity, placement)


@router.patch("/api/activities/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    database: Session = Depends(get_db),
) -> dict[str, object]:
    """Edit a manual activity and create, update, or remove its itinerary placement."""
    activity = require_activity(activity_id, database)
    trip = require_trip(activity.trip_id, database)
    activity.name = payload.name.strip()
    activity.normalized_name = normalize_name(payload.name)
    activity.category = payload.category.strip()
    activity.address = payload.address.strip()
    placement = scheduled_record(activity_id, database)

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

    database.commit()
    database.refresh(activity)
    if placement:
        database.refresh(placement)
    return serialize_activity(activity, placement)


@router.delete("/api/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int, database: Session = Depends(get_db)) -> None:
    """Delete an activity and any itinerary placement that belongs to it."""
    activity = require_activity(activity_id, database)
    placement = scheduled_record(activity.id, database)
    if placement:
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
    database.commit()
