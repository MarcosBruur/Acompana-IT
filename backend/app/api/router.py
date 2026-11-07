from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.profile.router import router as profile_router
from app.modules.vacancies.router import router as vacancies_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(vacancies_router)


@router.get("/health", tags=["salud"])
def health() -> dict[str, str]:
    return {"status": "ok"}
