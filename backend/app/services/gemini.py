"""Server-side Gemini calls for structured activity extraction and POI enrichment."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from ..categories import ACTIVITY_CATEGORIES, canonical_category


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class GeminiError(Exception):
    """Represent a Gemini request or structured-response failure safe to show to a user."""


@dataclass(frozen=True)
class ExtractedActivity:
    """A normalized activity and its distinct POI derived from social-video context."""

    activity_name: str
    categories: list[str]
    poi_name: str
    poi_address: str | None
    estimated_cost: str | None


def get_gemini_api_key() -> str:
    """Read the Gemini credential without ever returning it through an API response."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
    return api_key


def interaction_output(payload: dict[str, object]) -> str:
    """Extract generated text from Gemini's documented Interactions API response shape."""
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    steps = payload.get("steps")
    if isinstance(steps, list):
        text_parts: list[str] = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
        if text := "".join(text_parts).strip():
            return text
    raise GeminiError("Gemini returned no structured text output.")


def call_gemini_json(prompt: str, schema: dict[str, object]) -> dict[str, object]:
    """Request JSON-schema-constrained output from Gemini's Interactions REST API."""
    body = json.dumps(
        {
            "model": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            "input": prompt,
            "generation_config": {"temperature": 0.2, "thinking_level": "low"},
            "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
        }
    ).encode("utf-8")
    request = Request(
        GEMINI_INTERACTIONS_URL,
        data=body,
        headers={"x-goog-api-key": get_gemini_api_key(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - provider URL is a module constant.
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 429:
            raise GeminiError("Gemini's request quota is temporarily exhausted. Please wait a minute and try again.") from error
        raise GeminiError("Gemini could not complete this request. Please try again.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GeminiError("Gemini could not complete this request. Please try again.") from error
    try:
        result = json.loads(interaction_output(payload))
    except json.JSONDecodeError as error:
        raise GeminiError("Gemini returned invalid structured data. Please try again.") from error
    if not isinstance(result, dict):
        raise GeminiError("Gemini returned an unexpected structured response.")
    return result


def nonempty_string(value: object) -> str:
    """Validate required model string fields before any candidate reaches the API layer."""
    text = str(value or "").strip()
    if not text:
        raise GeminiError("Gemini returned an incomplete activity. Please try again.")
    return text


def categories_from_model(value: object) -> list[str]:
    """Validate, deduplicate, and bound the practical categories returned by Gemini."""
    if not isinstance(value, list):
        raise GeminiError("Gemini returned an incomplete activity. Please try again.")
    categories: list[str] = []
    seen: set[str] = set()
    for item in value:
        category = canonical_category(item)
        if not category:
            raise GeminiError("Gemini returned an unsupported activity category. Please try again.")
        key = category.casefold()
        if key in seen:
            continue
        seen.add(key)
        categories.append(category[:80])
    if not categories:
        raise GeminiError("Gemini returned an incomplete activity. Please try again.")
    return categories[:5]


def extract_activities(
    destination: str,
    caption: str,
    transcript: str | None,
) -> list[ExtractedActivity]:
    """Extract individual activity/POI candidates from TikTok metadata and spoken text."""
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "activities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "activity_name": {"type": "string"},
                        "categories": {"type": "array", "items": {"type": "string", "enum": list(ACTIVITY_CATEGORIES)}, "minItems": 1, "maxItems": 5},
                        "poi_name": {"type": "string"},
                        "poi_address": {"type": "string", "description": "Address when stated, otherwise an empty string."},
                        "estimated_cost": {"type": "string", "description": "Cost when stated, otherwise an empty string."},
                    },
                    "required": ["activity_name", "categories", "poi_name", "poi_address", "estimated_cost"],
                },
            }
        },
        "required": ["activities"],
    }
    prompt = f"""Extract travel activities mentioned in this TikTok context for a trip to {destination or 'the destination'}.
Create one item for each distinct activity and its place of interest (POI). Do not invent names, addresses, costs, or facts. Return one to five categories, using only these exact labels: {', '.join(ACTIVITY_CATEGORIES)}. Return an empty list if no identifiable activity and POI are mentioned.

Caption:
{caption}

Transcript:
{transcript or '(No speech-to-text transcript was available.)'}"""
    result = call_gemini_json(prompt, schema)
    records = result.get("activities")
    if not isinstance(records, list):
        raise GeminiError("Gemini returned an invalid activity list. Please try again.")
    candidates: list[ExtractedActivity] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        address_value = record.get("poi_address")
        candidates.append(
            ExtractedActivity(
                activity_name=nonempty_string(record.get("activity_name")),
                categories=categories_from_model(record.get("categories")),
                poi_name=nonempty_string(record.get("poi_name")),
                poi_address=str(address_value).strip() if address_value else None,
                estimated_cost=str(record.get("estimated_cost") or "").strip() or None,
            )
        )
    return candidates


def enrich_activity_data(name: str, address: str | None, destination: str) -> dict[str, dict[str, object]]:
    """Retrieve the three user-requested practical enrichment sections for one activity."""
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "food_and_consumption": {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "recommendations": {"type": "array", "items": {"type": "string"}}},
                "required": ["summary", "recommendations"],
            },
            "practical_visiting_information": {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "details": {"type": "array", "items": {"type": "string"}}},
                "required": ["summary", "details"],
            },
            "vibe_context_highlights": {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "highlights": {"type": "array", "items": {"type": "string"}}},
                "required": ["summary", "highlights"],
            },
        },
        "required": ["food_and_consumption", "practical_visiting_information", "vibe_context_highlights"],
    }
    prompt = f"""Provide concise, travel-useful enrichment for the POI below. State uncertainty clearly and never fabricate specific operating hours, prices, reservation requirements, accessibility details, or menu items. Each section must be a JSON object containing only useful known information.

POI: {name}
Address/context: {address or 'Not provided'}
Trip destination: {destination or 'Not provided'}"""
    result = call_gemini_json(prompt, schema)
    sections: dict[str, dict[str, object]] = {}
    for key in ("food_and_consumption", "practical_visiting_information", "vibe_context_highlights"):
        value = result.get(key)
        if not isinstance(value, dict):
            raise GeminiError("Gemini returned incomplete POI enrichment. Please try again.")
        sections[key] = value
    return sections
