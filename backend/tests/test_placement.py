"""Tests for edge cases in automatic itinerary placement."""

from datetime import date, time
from types import SimpleNamespace
import unittest

from app.routers.enrichment import place_approved_activity
from app.models import ScheduledActivity


class EmptyItineraryQuery:
    """Minimal query double returning no scheduled activity rows."""

    def join(self, *_args):
        """Support the placement query's join chain."""
        return self

    def filter(self, *_args):
        """Support the placement query's filter chain."""
        return self

    def order_by(self, *_args):
        """Support the placement query's ordering chain."""
        return self

    def all(self):
        """Return an itinerary with no scheduled events."""
        return []


class EmptyItinerarySession:
    """Minimal session double that captures a scheduled child created by placement."""

    def __init__(self) -> None:
        """Initialize the captured persistence list."""
        self.added: list[object] = []

    def query(self, *_args):
        """Return the empty-itinerary query double."""
        return EmptyItineraryQuery()

    def add(self, record: object) -> None:
        """Capture an object the placement algorithm asks SQLAlchemy to persist."""
        self.added.append(record)


class PlacementTests(unittest.TestCase):
    """Verify placement succeeds safely before any itinerary event exists."""

    def test_schedules_first_activity_without_routes_call(self) -> None:
        """Make the approved activity the first trip event at the neutral midday default."""
        session = EmptyItinerarySession()
        activity = SimpleNamespace(id=9, scheduled=False)
        trip = SimpleNamespace(id=3, start_date=date(2026, 8, 1))

        result = place_approved_activity(activity, trip, session)

        self.assertTrue(result.scheduled)
        self.assertTrue(activity.scheduled)
        self.assertEqual(len(session.added), 1)
        placement = session.added[0]
        self.assertIsInstance(placement, ScheduledActivity)
        self.assertEqual(placement.scheduled_date, date(2026, 8, 1))
        self.assertEqual(placement.scheduled_time, time(12))
