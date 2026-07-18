from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - imports SQLAlchemy model metadata
from .database import Base, engine
from .routers import activities, health, trips, users, video_metadata


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create local SQLite tables before the API starts serving requests."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="JetSetGo API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(trips.router)
app.include_router(activities.router)
app.include_router(video_metadata.router)
app.include_router(users.router)
