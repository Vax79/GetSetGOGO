"""Regression tests for the lightweight sharing helpers and PDF export."""

from datetime import date, time
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Activity, ScheduledActivity, Trip, TripMember, User
from app.routers.trips import export_itinerary_pdf, update_trip
from app.schemas import TripUpdate
from app.services.collaboration import ensure_share_code, ensure_trip_member


class CollaborationAndExportTests(unittest.TestCase):
    """Exercise the share identity and PDF output without external services."""

    def setUp(self) -> None:
        """Build an isolated SQLite database for each collaboration test."""
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.database = sessionmaker(bind=self.engine)()
        self.trip = Trip(name="Kyoto, spring", destination_city="Kyoto", start_date=date(2026, 4, 1), end_date=date(2026, 4, 4))
        self.database.add(self.trip)
        self.database.commit()
        self.database.refresh(self.trip)

    def tearDown(self) -> None:
        """Close the isolated database session after a test completes."""
        self.database.close()
        self.engine.dispose()

    def test_share_code_and_display_name_membership_are_repeatable(self) -> None:
        """Generate one code and avoid duplicate memberships for the same display name."""
        first_code = ensure_share_code(self.trip, self.database)
        first_user = ensure_trip_member(self.trip, "Xavier", self.database)
        second_user = ensure_trip_member(self.trip, "Xavier", self.database)

        self.assertRegex(first_code, r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(first_user.id, second_user.id)
        self.assertEqual(1, self.database.query(User).count())
        self.assertEqual(1, self.database.query(TripMember).count())

    def test_pdf_export_contains_a_day_by_day_itinerary(self) -> None:
        """Create a downloadable PDF with the scheduled stop and each trip day."""
        activity = Activity(
            trip_id=self.trip.id,
            name="Tea, dessert; tasting",
            normalized_name="teadesserttasting",
            category="Food",
            address="Gion, Kyoto",
            estimated_cost="$18",
            scheduled=True,
        )
        self.database.add(activity)
        self.database.flush()
        self.database.add(ScheduledActivity(activity_id=activity.id, scheduled_date=date(2026, 4, 2), scheduled_time=time(14, 30), sort_order=1))
        self.database.commit()

        response = export_itinerary_pdf(self.trip.id, self.database)
        document = response.body

        self.assertTrue(document.startswith(b"%PDF-1.4"))
        self.assertIn(b"DAY 2  |  Thursday, April 2, 2026", document)
        self.assertIn(b"2:30 PM", document)
        self.assertIn(b"Tea, dessert; tasting", document)
        self.assertIn('attachment; filename="kyoto-spring-itinerary.pdf"', response.headers["content-disposition"])

    def test_updates_trip_information_when_all_scheduled_items_stay_in_range(self) -> None:
        """Persist edited trip text and dates when no itinerary activity is excluded."""
        updated = update_trip(
            self.trip.id,
            TripUpdate(name="Kyoto food week", destination_city="Kyoto", destination_region="Kansai", start_date=date(2026, 3, 31), end_date=date(2026, 4, 5)),
            self.database,
        )

        self.assertEqual("Kyoto food week", updated.name)
        self.assertEqual(date(2026, 3, 31), updated.start_date)

    def test_rejects_trip_dates_that_exclude_a_scheduled_activity(self) -> None:
        """Keep existing itinerary placements valid when a user shortens a trip."""
        activity = Activity(trip_id=self.trip.id, name="Kiyomizu", normalized_name="kiyomizu", category="Culture", address="Kyoto", scheduled=True)
        self.database.add(activity)
        self.database.flush()
        self.database.add(ScheduledActivity(activity_id=activity.id, scheduled_date=date(2026, 4, 4), scheduled_time=time(10), sort_order=1))
        self.database.commit()

        with self.assertRaises(HTTPException) as error:
            update_trip(
                self.trip.id,
                TripUpdate(name="Kyoto", destination_city="Kyoto", destination_region=None, start_date=date(2026, 4, 1), end_date=date(2026, 4, 3)),
                self.database,
            )
        self.assertEqual(422, error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
