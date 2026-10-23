from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/health", tags=["salud"])
def health() -> dict[str, str]:
    return {"status": "ok"}
