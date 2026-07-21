"""The fixed activity taxonomy shared by extraction and manual entry."""

ACTIVITY_CATEGORIES = (
    "Food",
    "Shopping",
    "Sightseeing",
    "Culture",
    "Nature",
    "Nightlife",
    "Wellness",
    "Entertainment",
    "Activities",
    "Accommodation",
    "Transport",
)

CATEGORY_BY_KEY = {category.casefold(): category for category in ACTIVITY_CATEGORIES}


def canonical_category(value: object) -> str | None:
    """Return a fixed category label for a case-insensitive input, when supported."""
    return CATEGORY_BY_KEY.get(str(value or "").strip().casefold())
