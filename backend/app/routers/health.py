from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Report that the API process is available for frontend connectivity checks."""
    return {"status": "ok", "service": "jetsetgo-api"}
