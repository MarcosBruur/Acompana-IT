from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.modules.auth.router import Database
from app.modules.auth.router import router as auth_router
from app.modules.interviews.router import router as interviews_router
from app.modules.profile.router import router as profile_router
from app.modules.vacancies.router import router as vacancies_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(vacancies_router)
router.include_router(interviews_router)


@router.get("/health", tags=["salud"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["salud"])
def ready(db: Database) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "La base de datos no está disponible.") from None
    return {"status": "ok"}
