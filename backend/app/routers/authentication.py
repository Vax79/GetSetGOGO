"""Public registration and login endpoints for JetSetGo username/password accounts."""

from collections.abc import Generator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..auth import bearer_scheme, create_session, normalize_username, password_hash, require_current_user, token_digest, verify_password
from ..database import SessionLocal
from ..models import Activity, AuthSession, Trip, TripMember, User, Vote
from ..schemas import AuthSessionRead, PasswordLogin, PasswordRegister, UserRead


router = APIRouter(prefix="/api/auth", tags=["authentication"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a public authentication request."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def adopt_legacy_profile(legacy: User, account: User, database: Session) -> None:
    """Move migrated trip records from a display-name-only profile to a password account."""
    for membership in database.query(TripMember).filter_by(user_id=legacy.id).all():
        if database.query(TripMember).filter_by(trip_id=membership.trip_id, user_id=account.id).one_or_none():
            database.delete(membership)
        else:
            membership.user_id = account.id
    for vote in database.query(Vote).filter_by(user_id=legacy.id).all():
        if database.query(Vote).filter_by(activity_id=vote.activity_id, user_id=account.id).one_or_none():
            database.delete(vote)
        else:
            vote.user_id = account.id
    database.query(Activity).filter_by(submitted_by_id=legacy.id).update({Activity.submitted_by_id: account.id})
    database.query(Trip).filter_by(owner_user_id=legacy.id).update({Trip.owner_user_id: account.id})
    database.delete(legacy)


def auth_response(user: User, database: Session) -> AuthSessionRead:
    """Commit one new session and package the token with its safe user profile."""
    token, _ = create_session(user, database)
    database.commit()
    database.refresh(user)
    return AuthSessionRead(access_token=token, user=UserRead.model_validate(user))


@router.post("/register", response_model=AuthSessionRead, status_code=status.HTTP_201_CREATED)
def register(payload: PasswordRegister, database: Session = Depends(get_db)) -> AuthSessionRead:
    """Create a username account or claim a matching migrated display-name profile."""
    username = normalize_username(payload.username)
    display_name = payload.display_name.strip()
    if database.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="That username is already taken.")
    legacy = database.query(User).filter(User.name == display_name, User.username.is_(None), User.password_hash.is_(None)).first()
    if legacy:
        legacy.username = username
        legacy.password_hash = password_hash(payload.password)
        return auth_response(legacy, database)
    user = User(username=username, password_hash=password_hash(payload.password), name=display_name)
    database.add(user)
    database.flush()
    return auth_response(user, database)


@router.post("/login", response_model=AuthSessionRead)
def login(payload: PasswordLogin, database: Session = Depends(get_db)) -> AuthSessionRead:
    """Authenticate by username and return a new opaque bearer session."""
    user = database.query(User).filter_by(username=normalize_username(payload.username)).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    return auth_response(user, database)


@router.get("/me", response_model=UserRead)
def current_account(user: User = Depends(require_current_user)) -> User:
    """Return the currently authenticated username account."""
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    database: Session = Depends(get_db),
    _: User = Depends(require_current_user),
) -> None:
    """Revoke the current opaque session so its token cannot be reused."""
    if credentials:
        database.query(AuthSession).filter_by(token_digest=token_digest(credentials.credentials)).delete()
        database.commit()
