"""Google Routes API adapter for distance-based itinerary placement."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

ROUTE_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
ROUTE_MATRIX_FIELD_MASK = "originIndex,destinationIndex,status,condition,distanceMeters,duration"


class RoutesError(Exception):
    """Represent a Google Routes failure that leaves an approved activity safely unscheduled."""


@dataclass(frozen=True)
class RouteMetric:
    """Travel distance and duration between a new activity and one scheduled activity."""

    distance_meters: int
    duration_seconds: int | None


def get_routes_api_key() -> str:
    """Read a dedicated Routes key or reuse the Places key when Routes is enabled on it."""
    api_key = os.getenv("GOOGLE_ROUTES_API_KEY", "").strip() or os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise RoutesError("Google Routes is not configured. Add GOOGLE_ROUTES_API_KEY to .env.")
    return api_key


def waypoint(latitude: str, longitude: str) -> dict[str, object]:
    """Build a Routes API latitude/longitude waypoint from persisted activity coordinates."""
    try:
        return {"waypoint": {"location": {"latLng": {"latitude": float(latitude), "longitude": float(longitude)}}}}
    except (TypeError, ValueError) as error:
        raise RoutesError("An activity is missing valid coordinates for travel-distance placement.") from error


def parse_duration_seconds(value: object) -> int | None:
    """Convert the Routes API protobuf duration string, such as '160s', to seconds."""
    if not isinstance(value, str) or not value.endswith("s"):
        return None
    try:
        return round(float(value[:-1]))
    except ValueError:
        return None


def route_matrix(origin: tuple[str, str], destinations: list[tuple[str, str]]) -> dict[int, RouteMetric]:
    """Return drive-distance metrics from one new activity to every scheduled destination."""
    if not destinations:
        return {}
    payload = {"origins": [waypoint(*origin)], "destinations": [waypoint(*destination) for destination in destinations], "travelMode": "DRIVE"}
    request = Request(ROUTE_MATRIX_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "X-Goog-Api-Key": get_routes_api_key(), "X-Goog-FieldMask": ROUTE_MATRIX_FIELD_MASK}, method="POST")
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - Google Routes endpoint is a module constant.
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RoutesError("Google Routes could not calculate travel distances for placement.") from error
    if not isinstance(result, list):
        raise RoutesError("Google Routes returned an unexpected route matrix response.")
    metrics: dict[int, RouteMetric] = {}
    for row in result:
        if not isinstance(row, dict) or row.get("condition") != "ROUTE_EXISTS":
            continue
        destination_index = row.get("destinationIndex")
        distance = row.get("distanceMeters")
        if isinstance(destination_index, int) and isinstance(distance, int):
            metrics[destination_index] = RouteMetric(distance, parse_duration_seconds(row.get("duration")))
    return metrics
