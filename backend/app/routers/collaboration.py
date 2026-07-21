"""Trip-code sharing and visual-only preference voting endpoints."""

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..auth import require_current_user, require_trip_access
from ..models import Activity, Trip, TripMember, User, Vote
from ..schemas import (
    DisplayNameRequest,
    JoinTripRequest,
    JoinedTripRead,
    ShareTripRead,
    TripRead,
    UserRead,
    VoteCandidateRead,
    VoteRequest,
)
from ..services.collaboration import clean_display_name, ensure_share_code, ensure_user_membership

router = APIRouter(tags=["collaboration"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for sharing and voting requests."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def require_trip(trip_id: int, database: Session, current_user: User | None = None) -> Trip:
    """Return a trip or stop a collaboration operation with a consistent error."""
    trip = database.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    if current_user:
        membership = database.query(TripMember).filter_by(trip_id=trip.id, user_id=current_user.id).one_or_none()
        if not membership:
            raise HTTPException(status_code=403, detail="You do not have access to this trip.")
    else:
        require_trip_access(trip, database)
    return trip


def require_display_name(value: str) -> str:
    """Reject blank names because the PRD uses them as the collaborator identity."""
    name = clean_display_name(value)
    if not name:
        raise HTTPException(status_code=422, detail="Enter a display name before collaborating.")
    return name


def attached_user(current_user: User, database: Session) -> User:
    """Load the authenticated account into this request's session before mutating memberships or votes."""
    user = database.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="Your account could not be found.")
    return user


@router.get("/api/trips/{trip_id}/share", response_model=ShareTripRead)
def get_share_link(
    trip_id: int,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> ShareTripRead:
    """Return the existing or newly created code used to join a trip."""
    trip = require_trip(trip_id, database, current_user)
    code = ensure_share_code(trip, database)
    database.commit()
    return ShareTripRead(share_code=code)


@router.get("/api/trips/{trip_id}/members", response_model=list[UserRead])
def list_trip_members(
    trip_id: int,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> list[User]:
    """Return the signed-in collaborators who currently have access to a trip."""
    trip = require_trip(trip_id, database, current_user)
    return (
        database.query(User)
        .join(TripMember, TripMember.user_id == User.id)
        .filter(TripMember.trip_id == trip.id)
        .order_by(User.name.asc())
        .all()
    )


@router.post("/api/trips/{trip_id}/members", response_model=UserRead)
def join_known_trip(
    trip_id: int,
    payload: DisplayNameRequest,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> User:
    """Attach the current local display-name user to a trip they already opened."""
    trip = require_trip(trip_id, database, current_user)
    user = ensure_user_membership(trip, attached_user(current_user, database), database)
    database.commit()
    database.refresh(user)
    return user


@router.post("/api/trips/join", response_model=JoinedTripRead)
def join_shared_trip(
    payload: JoinTripRequest,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> JoinedTripRead:
    """Join a trip by code and retain a display-name-only collaborator identity."""
    code = payload.share_code.strip().upper()
    trip = database.query(Trip).filter_by(share_code=code).one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="That trip code was not found.")
    user = ensure_user_membership(trip, attached_user(current_user, database), database)
    database.commit()
    database.refresh(trip)
    database.refresh(user)
    return JoinedTripRead(trip=TripRead.model_validate(trip), user=UserRead.model_validate(user))


@router.get("/api/trips/{trip_id}/vote-candidates", response_model=list[VoteCandidateRead])
def list_vote_candidates(
    trip_id: int,
    display_name: str,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> list[VoteCandidateRead]:
    """Return approved activities the named collaborator has not yet voted on."""
    require_trip(trip_id, database, current_user)
    require_display_name(display_name)
    user = attached_user(current_user, database)
    voted_activity_ids = database.query(Vote.activity_id).filter(Vote.user_id == user.id)
    records = (
        database.query(Activity, User.name, func.coalesce(func.sum(Vote.vote_value), 0))
        .outerjoin(User, User.id == Activity.submitted_by_id)
        .outerjoin(Vote, Vote.activity_id == Activity.id)
        .filter(Activity.trip_id == trip_id, ~Activity.id.in_(voted_activity_ids))
        .group_by(Activity.id, User.name)
        .order_by(Activity.created_at.desc())
        .all()
    )
    return [
        VoteCandidateRead(
            id=activity.id,
            name=activity.name,
            category=activity.category,
            address=activity.address,
            estimated_cost=activity.estimated_cost,
            scheduled=activity.scheduled,
            submitted_by=submitted_by,
            vote_score=int(score),
        )
        for activity, submitted_by, score in records
    ]


@router.post("/api/activities/{activity_id}/vote", response_model=VoteCandidateRead)
def cast_vote(
    activity_id: int,
    payload: VoteRequest,
    database: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
) -> VoteCandidateRead:
    """Persist one upvote or downvote without changing an activity's itinerary state."""
    activity = database.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found.")
    trip = require_trip(activity.trip_id, database, current_user)
    user = ensure_user_membership(trip, attached_user(current_user, database), database)
    vote = database.query(Vote).filter_by(activity_id=activity.id, user_id=user.id).one_or_none()
    if vote:
        vote.vote_value = payload.vote_value
    else:
        database.add(Vote(activity_id=activity.id, user_id=user.id, vote_value=payload.vote_value))
    database.commit()
    score = database.query(func.coalesce(func.sum(Vote.vote_value), 0)).filter(Vote.activity_id == activity.id).scalar() or 0
    submitted_by = database.query(User.name).filter(User.id == activity.submitted_by_id).scalar()
    return VoteCandidateRead(
        id=activity.id,
        name=activity.name,
        category=activity.category,
        address=activity.address,
        estimated_cost=activity.estimated_cost,
        scheduled=activity.scheduled,
        submitted_by=submitted_by,
        vote_score=int(score),
    )
