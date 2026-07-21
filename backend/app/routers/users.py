from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..database import SessionLocal
from ..models import Activity, Trip, TripMember, User, Vote
from ..schemas import DisplayNameRequest, UserRead


def get_db() -> Generator[Session, None, None]:
    """Provide a session for a signed-in user's profile update."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()

router = APIRouter(prefix="/api/users", tags=["users"])


def adopt_legacy_user(legacy: User, account: User, database: Session) -> None:
    """Move pre-Supabase user records to the authenticated account without duplicate memberships or votes."""
    for membership in database.query(TripMember).filter_by(user_id=legacy.id).all():
        existing = database.query(TripMember).filter_by(trip_id=membership.trip_id, user_id=account.id).one_or_none()
        if existing:
            database.delete(membership)
        else:
            membership.user_id = account.id

    for vote in database.query(Vote).filter_by(user_id=legacy.id).all():
        existing = database.query(Vote).filter_by(activity_id=vote.activity_id, user_id=account.id).one_or_none()
        if existing:
            database.delete(vote)
        else:
            vote.user_id = account.id

    database.query(Activity).filter_by(submitted_by_id=legacy.id).update({Activity.submitted_by_id: account.id})
    database.query(Trip).filter_by(owner_user_id=legacy.id).update({Trip.owner_user_id: account.id})
    database.delete(legacy)


@router.get("/me", response_model=UserRead)
def current_profile(user: User = Depends(require_current_user)) -> User:
    """Return the display identity attached to the authenticated Supabase user."""
    return user


@router.patch("/me", response_model=UserRead)
def update_profile(
    payload: DisplayNameRequest,
    database: Session = Depends(get_db),
    current: User = Depends(require_current_user),
) -> User:
    """Update the display name used when this account contributes to a trip."""
    name = payload.display_name.strip()[:80]
    if not name:
        raise HTTPException(status_code=422, detail="Enter a display name.")
    user = database.get(User, current.id)
    if not user:
        raise HTTPException(status_code=401, detail="Your account could not be found.")
    legacy = database.query(User).filter(User.auth_subject.is_(None), User.name == name, User.id != user.id).first()
    if legacy:
        adopt_legacy_user(legacy, user, database)
    user.name = name
    database.commit()
    database.refresh(user)
    return user
