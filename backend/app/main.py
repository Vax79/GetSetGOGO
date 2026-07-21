from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401 - imports SQLAlchemy model metadata
from .database import Base, engine
from .auth import require_current_user
from .routers import activities, authentication, collaboration, enrichment, health, trips, users, video_metadata


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def apply_sqlite_migrations() -> None:
    """Add nullable cached-route columns to existing local SQLite databases when needed."""
    columns = {column["name"] for column in inspect(engine).get_columns("scheduled_activities")}
    migrations = {
        "route_from_activity_id": "ALTER TABLE scheduled_activities ADD COLUMN route_from_activity_id INTEGER",
        "route_polyline": "ALTER TABLE scheduled_activities ADD COLUMN route_polyline TEXT",
        "route_distance_meters": "ALTER TABLE scheduled_activities ADD COLUMN route_distance_meters INTEGER",
        "route_duration_seconds": "ALTER TABLE scheduled_activities ADD COLUMN route_duration_seconds INTEGER",
    }
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables and retain legacy SQLite route-cache support locally."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        apply_sqlite_migrations()
    yield


app = FastAPI(title="JetSetGo API", version="0.1.0", lifespan=lifespan)
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(authentication.router)
app.include_router(trips.router, dependencies=[Depends(require_current_user)])
app.include_router(activities.router, dependencies=[Depends(require_current_user)])
app.include_router(collaboration.router, dependencies=[Depends(require_current_user)])
app.include_router(enrichment.router, dependencies=[Depends(require_current_user)])
app.include_router(video_metadata.router, dependencies=[Depends(require_current_user)])
app.include_router(users.router, dependencies=[Depends(require_current_user)])
