"""Google Places (New) geocoding helpers for extracted travel activities."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

PLACES_API_BASE_URL = "https://places.googleapis.com/v1"
TEXT_SEARCH_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location"
PLACE_DETAILS_FIELD_MASK = "displayName,formattedAddress,location,regularOpeningHours"


class GeocodingError(Exception):
    """Represent a Google Places lookup problem safe to return to the client."""


@dataclass(frozen=True)
class GeocodedPlace:
    """The geocoding fields persisted against an activity after a strong Places match."""

    name: str
    address: str | None
    latitude: str | None
    longitude: str | None
    operating_hours: str | None


def get_places_api_key() -> str:
    """Read the server-only Places credential without exposing it through application responses."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise GeocodingError("Google Places is not configured. Add GOOGLE_PLACES_API_KEY to .env.")
    return api_key


def request_places_json(url: str, method: str, field_mask: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    """Call a fixed Google Places endpoint with its required key and response field mask."""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": get_places_api_key(),
            "X-Goog-FieldMask": field_mask,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - URLs are module constants or Google resource paths.
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GeocodingError("Google Places could not resolve this location. Please try again.") from error
    if not isinstance(result, dict):
        raise GeocodingError("Google Places returned an unexpected location response.")
    return result


def display_name(place: dict[str, object], fallback: str) -> str:
    """Read a human-facing Place display name while preserving the supplied location as fallback."""
    value = place.get("displayName")
    if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"].strip():
        return value["text"].strip()
    return fallback


def coordinate(place: dict[str, object], key: str) -> str | None:
    """Normalize a Google Places latitude or longitude number into the activity string column."""
    location = place.get("location")
    value = location.get(key) if isinstance(location, dict) else None
    return str(value) if isinstance(value, (int, float)) else None


def regular_hours(place: dict[str, object]) -> str | None:
    """Store the provider's regular opening-hour structure as JSON for later display and scheduling."""
    hours = place.get("regularOpeningHours")
    return json.dumps(hours) if isinstance(hours, dict) else None


def geocode_place(location_name: str, destination: str) -> GeocodedPlace:
    """Resolve a location through Text Search, then fetch its coordinates and operating hours."""
    query = ", ".join(part.strip() for part in (location_name, destination) if part and part.strip())
    if not query:
        raise GeocodingError("A location name is required for geocoding.")
    search = request_places_json(
        f"{PLACES_API_BASE_URL}/places:searchText",
        "POST",
        TEXT_SEARCH_FIELD_MASK,
        {"textQuery": query, "pageSize": 1},
    )
    matches = search.get("places")
    if not isinstance(matches, list) or not matches or not isinstance(matches[0], dict):
        raise GeocodingError("Google Places could not find this location in the trip destination.")
    match = matches[0]
    place_id = match.get("id")
    if not isinstance(place_id, str) or not place_id.strip():
        raise GeocodingError("Google Places returned a location without a place ID.")
    details = request_places_json(
        f"{PLACES_API_BASE_URL}/places/{quote(place_id, safe='')}",
        "GET",
        PLACE_DETAILS_FIELD_MASK,
    )
    return GeocodedPlace(
        name=display_name(details, display_name(match, location_name)),
        address=str(details.get("formattedAddress") or match.get("formattedAddress") or "").strip() or None,
        latitude=coordinate(details, "latitude") or coordinate(match, "latitude"),
        longitude=coordinate(details, "longitude") or coordinate(match, "longitude"),
        operating_hours=regular_hours(details),
    )
