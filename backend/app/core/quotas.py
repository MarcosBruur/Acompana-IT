"""Cupos persistentes por candidato; las filas ocultas no ocupan espacio."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Candidate, Interview, Resume, Vacancy, VacancyAnalysis


def check_resume_quota(db: Session, candidate: Candidate) -> None:
    if candidate.admin:
        return
    count = db.scalar(select(func.count(Resume.id)).where(
        Resume.candidate_id == candidate.id, Resume.active.is_(True)))
    if count >= 5:
        raise HTTPException(409, "Ya tenés 5 CV activos. Ocultá uno antes de subir otro.")


def check_vacancy_quota(db: Session, candidate: Candidate) -> None:
    if candidate.admin:
        return
    count = db.scalar(select(func.count(Vacancy.id)).join(VacancyAnalysis).where(
        Vacancy.candidate_id == candidate.id, Vacancy.active.is_(True)))
    if count >= 20:
        raise HTTPException(409, "Ya tenés 20 vacantes analizadas activas. Ocultá una antes de analizar otra.")


def check_interview_quota(db: Session, candidate: Candidate) -> None:
    if candidate.admin:
        return
    recent = db.scalar(select(func.count(Interview.id)).where(
        Interview.candidate_id == candidate.id,
        Interview.created_at >= datetime.now(UTC) - timedelta(hours=24)))
    if recent >= 10:
        raise HTTPException(429, "Ya iniciaste 10 entrevistas en las últimas 24 horas. Intentá más tarde.")
    saved = db.scalar(select(func.count(Interview.id)).where(
        Interview.candidate_id == candidate.id, Interview.active.is_(True),
        Interview.status == "completed", Interview.score.is_not(None)))
    if saved >= 20:
        raise HTTPException(409, "Ya tenés 20 resultados de entrevistas guardados. Ocultá uno antes de iniciar otra simulación.")
