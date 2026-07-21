"""Small helpers for the PRD's display-name collaboration model."""

import secrets
import string

from sqlalchemy.orm import Session

from ..models import Trip, TripMember, User


def clean_display_name(value: str | None) -> str | None:
    """Trim a collaborator name while treating a blank optional value as absent."""
    return value.strip()[:80] if value and value.strip() else None


def get_or_create_user(display_name: str, database: Session) -> User:
    """Return the unique lightweight user identified only by their display name."""
    name = clean_display_name(display_name)
    if not name:
        raise ValueError("Enter a display name before collaborating.")
    user = database.query(User).filter_by(name=name).one_or_none()
    if user:
        return user
    user = User(name=name)
    database.add(user)
    database.flush()
    return user


def ensure_trip_member(trip: Trip, display_name: str, database: Session) -> User:
    """Create the display-name user and trip membership when either is missing."""
    user = get_or_create_user(display_name, database)
    membership = database.query(TripMember).filter_by(trip_id=trip.id, user_id=user.id).one_or_none()
    if not membership:
        database.add(TripMember(trip_id=trip.id, user_id=user.id))
        database.flush()
    return user


def ensure_user_membership(trip: Trip, user: User, database: Session) -> User:
    """Attach an already authenticated user to a trip without display-name matching."""
    membership = database.query(TripMember).filter_by(trip_id=trip.id, user_id=user.id).one_or_none()
    if not membership:
        database.add(TripMember(trip_id=trip.id, user_id=user.id))
        database.flush()
    return user


def new_share_code(database: Session) -> str:
    """Generate a concise collision-free code that can be shared without a login."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))
        if not database.query(Trip).filter_by(share_code=code).first():
            return code


def ensure_share_code(trip: Trip, database: Session) -> str:
    """Give existing trips a code lazily, so old local data remains shareable."""
    if not trip.share_code:
        trip.share_code = new_share_code(database)
        database.flush()
    return trip.share_code
