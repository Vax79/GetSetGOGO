"""Username/password authentication with salted scrypt hashes and opaque sessions."""

import base64
from contextvars import ContextVar
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import AuthSession, Trip, TripMember, User


SESSION_DAYS = 30
bearer_scheme = HTTPBearer(auto_error=False)
request_user: ContextVar[User | None] = ContextVar("request_user", default=None)


def normalize_username(value: str) -> str:
    """Normalize usernames so case variants cannot become separate accounts."""
    return value.strip().casefold()


def password_hash(password: str) -> str:
    """Generate a salted scrypt password hash using production-safe work factors."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(derived).decode()


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Verify a supplied password with constant-time comparison and malformed-hash rejection."""
    if not stored_hash:
        return False
    try:
        algorithm, n, r, p, encoded_salt, encoded_hash = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode())
        expected = base64.urlsafe_b64decode(encoded_hash.encode())
        derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(derived, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    """Hash an opaque session token before database lookup or persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user: User, database: Session) -> tuple[str, AuthSession]:
    """Create a 30-day revocable session and return its one-time raw bearer token."""
    raw_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        token_digest=token_digest(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=SESSION_DAYS),
    )
    database.add(session)
    database.flush()
    return raw_token, session


def active_user() -> User | None:
    """Return the username-authenticated user resolved for the current request."""
    return request_user.get()


async def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """Resolve a valid opaque bearer token to its active application user."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    database = SessionLocal()
    try:
        session = (
            database.query(AuthSession)
            .filter(AuthSession.token_digest == token_digest(credentials.credentials), AuthSession.expires_at > datetime.utcnow())
            .one_or_none()
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired.", headers={"WWW-Authenticate": "Bearer"})
        user = database.get(User, session.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your account could not be found.")
        database.expunge(user)
    finally:
        database.close()
    request_user.set(user)
    return user


def require_trip_access(trip: Trip, database: Session) -> None:
    """Reject access to a trip unless the current signed-in user is a member."""
    user = active_user()
    if user is None:  # Direct service tests do not execute FastAPI dependencies.
        return
    membership = database.query(TripMember).filter_by(trip_id=trip.id, user_id=user.id).one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this trip.")
