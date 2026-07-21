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
COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
COMPUTE_ROUTES_FIELD_MASK = "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"
ITINERARY_ROUTES_FIELD_MASK = "routes.legs.distanceMeters,routes.legs.duration,routes.legs.polyline.encodedPolyline"


class RoutesError(Exception):
    """Represent a Google Routes failure that leaves an approved activity safely unscheduled."""


@dataclass(frozen=True)
class RouteMetric:
    """Travel distance and duration between a new activity and one scheduled activity."""

    distance_meters: int
    duration_seconds: int | None


@dataclass(frozen=True)
class RoutePath:
    """A placement-time route path that the frontend can draw without another Routes request."""

    encoded_polyline: str
    distance_meters: int | None
    duration_seconds: int | None


def get_routes_api_key() -> str:
    """Read the shared Google Maps key, retaining legacy aliases as a fallback."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip() or os.getenv("GOOGLE_ROUTES_API_KEY", "").strip() or os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise RoutesError("Google Routes is not configured. Add GOOGLE_MAPS_API_KEY to .env.")
    return api_key


def route_waypoint(latitude: str, longitude: str) -> dict[str, object]:
    """Build a Compute Routes waypoint from persisted activity coordinates."""
    try:
        return {"location": {"latLng": {"latitude": float(latitude), "longitude": float(longitude)}}}
    except (TypeError, ValueError) as error:
        raise RoutesError("An activity is missing valid coordinates for travel-distance placement.") from error


def matrix_waypoint(latitude: str, longitude: str) -> dict[str, object]:
    """Wrap a waypoint in the Route Matrix origin or destination shape."""
    return {"waypoint": route_waypoint(latitude, longitude)}


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
    payload = {"origins": [matrix_waypoint(*origin)], "destinations": [matrix_waypoint(*destination) for destination in destinations], "travelMode": "DRIVE"}
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


def compute_route(origin: tuple[str, str], destination: tuple[str, str]) -> RoutePath:
    """Compute one placement route and retain its encoded polyline for later map rendering."""
    payload = {"origin": route_waypoint(*origin), "destination": route_waypoint(*destination), "travelMode": "DRIVE"}
    request = Request(
        COMPUTE_ROUTES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": get_routes_api_key(), "X-Goog-FieldMask": COMPUTE_ROUTES_FIELD_MASK},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - Google Routes endpoint is a module constant.
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RoutesError("Google Routes could not calculate a route path for the map.") from error
    routes = result.get("routes") if isinstance(result, dict) else None
    route = routes[0] if isinstance(routes, list) and routes and isinstance(routes[0], dict) else None
    polyline = route.get("polyline") if isinstance(route, dict) else None
    encoded = polyline.get("encodedPolyline") if isinstance(polyline, dict) else None
    if not isinstance(encoded, str) or not encoded:
        raise RoutesError("Google Routes returned no usable route polyline.")
    distance = route.get("distanceMeters")
    return RoutePath(
        encoded_polyline=encoded,
        distance_meters=distance if isinstance(distance, int) else None,
        duration_seconds=parse_duration_seconds(route.get("duration")),
    )


def compute_itinerary_route(stops: list[tuple[str, str]]) -> list[RoutePath]:
    """Calculate every consecutive itinerary leg in one Google Routes request."""
    if len(stops) < 2:
        return []
    if len(stops) > 27:
        raise RoutesError("Google Routes supports at most 27 ordered stops in one itinerary route.")

    payload: dict[str, object] = {
        "origin": route_waypoint(*stops[0]),
        "destination": route_waypoint(*stops[-1]),
        "travelMode": "DRIVE",
    }
    if len(stops) > 2:
        payload["intermediates"] = [route_waypoint(*stop) for stop in stops[1:-1]]
    request = Request(
        COMPUTE_ROUTES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": get_routes_api_key(), "X-Goog-FieldMask": ITINERARY_ROUTES_FIELD_MASK},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - Google Routes endpoint is a module constant.
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RoutesError("Google Routes could not calculate travel times for this itinerary.") from error

    routes = result.get("routes") if isinstance(result, dict) else None
    route = routes[0] if isinstance(routes, list) and routes and isinstance(routes[0], dict) else None
    legs = route.get("legs") if isinstance(route, dict) else None
    if not isinstance(legs, list) or len(legs) != len(stops) - 1:
        raise RoutesError("Google Routes returned incomplete itinerary travel times.")

    paths: list[RoutePath] = []
    for leg in legs:
        polyline = leg.get("polyline") if isinstance(leg, dict) else None
        encoded = polyline.get("encodedPolyline") if isinstance(polyline, dict) else None
        if not isinstance(encoded, str) or not encoded:
            raise RoutesError("Google Routes returned an itinerary leg without a usable path.")
        distance = leg.get("distanceMeters")
        paths.append(
            RoutePath(
                encoded_polyline=encoded,
                distance_meters=distance if isinstance(distance, int) else None,
                duration_seconds=parse_duration_seconds(leg.get("duration")),
            )
        )
    return paths
