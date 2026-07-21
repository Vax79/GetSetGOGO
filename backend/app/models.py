from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    destination_city: Mapped[str | None] = mapped_column(String(120))
    destination_region: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    share_code: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    auth_subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    normalized_name: Mapped[str] = mapped_column(String(180), index=True)
    category: Mapped[str] = mapped_column(String(80))
    categories: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[str | None] = mapped_column(String(32))
    longitude: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(255))
    operating_hours: Mapped[str | None] = mapped_column(Text)
    estimated_cost: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    enrichment_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScheduledActivity(Base):
    """Itinerary-specific timing for a reusable approved activity."""

    __tablename__ = "scheduled_activities"
    __table_args__ = (UniqueConstraint("activity_id", name="uq_scheduled_activity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_time: Mapped[time | None] = mapped_column(Time)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    route_from_activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    route_polyline: Mapped[str | None] = mapped_column(Text)
    route_distance_meters: Mapped[int | None] = mapped_column(Integer)
    route_duration_seconds: Mapped[int | None] = mapped_column(Integer)


class TripMember(Base):
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("activity_id", "user_id", name="uq_activity_vote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vote_value: Mapped[int] = mapped_column(Integer)


class AuthSession(Base):
    """A revocable, opaque browser session whose raw token is never persisted."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
