from fastapi import APIRouter

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users() -> list[object]:
    """Return an empty placeholder until lightweight user handling is implemented."""
    return []
