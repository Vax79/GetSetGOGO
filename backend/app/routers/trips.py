from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Trip
from ..schemas import TripCreate, TripRead

router = APIRouter(prefix="/api/trips", tags=["trips"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a trip request and close it afterward."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def optional_text(value: str | None) -> str | None:
    """Normalize optional form strings so blank values are stored as NULL."""
    if value is None:
        return None
    return value.strip() or None


@router.get("", response_model=list[TripRead])
def list_trips(database: Session = Depends(get_db)) -> list[Trip]:
    """Return all trips with the most recently created first."""
    return database.query(Trip).order_by(Trip.created_at.desc()).all()


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripCreate, database: Session = Depends(get_db)) -> Trip:
    """Validate and persist a new trip before activity planning begins."""
    city = optional_text(payload.destination_city)
    region = optional_text(payload.destination_region)
    name = payload.name.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Trip name is required.")
    if not city and not region:
        raise HTTPException(status_code=422, detail="Enter a destination city or region.")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be before the start date.")

    trip = Trip(
        name=name,
        destination_city=city,
        destination_region=region,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    database.add(trip)
    database.commit()
    database.refresh(trip)
    return trip
