"""Historial privado de entrevistas terminadas y sus resultados guardados."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Interview, Vacancy
from app.modules.auth.router import ActiveCandidate, Database

router = APIRouter(prefix="/interviews", tags=["entrevistas"])


class InterviewSummary(BaseModel):
    id: int
    vacancy_title: str
    created_at: datetime
    score: int


class InterviewResult(InterviewSummary):
    feedback: str | None
    skills_to_improve: list[str]


@router.get("", response_model=list[InterviewSummary])
def history(candidate: ActiveCandidate, db: Database):
    rows = db.execute(
        select(Interview, Vacancy.title)
        .join(Vacancy, Interview.vacancy_id == Vacancy.id)
        .where(Interview.candidate_id == candidate.id,
               Interview.active.is_(True), Interview.status == "completed",
               Interview.score.is_not(None))
        .order_by(Interview.created_at.desc(), Interview.id.desc())
    ).all()
    return [InterviewSummary(id=interview.id, vacancy_title=title,
                             created_at=interview.created_at, score=interview.score)
            for interview, title in rows]


@router.get("/{interview_id}", response_model=InterviewResult)
def result(interview_id: int, candidate: ActiveCandidate, db: Database):
    row = db.execute(
        select(Interview, Vacancy.title)
        .join(Vacancy, Interview.vacancy_id == Vacancy.id)
        .where(Interview.id == interview_id, Interview.candidate_id == candidate.id,
               Interview.status == "completed", Interview.score.is_not(None))
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Entrevista no encontrada.")
    interview, title = row
    return InterviewResult(id=interview.id, vacancy_title=title,
                           created_at=interview.created_at, score=interview.score,
                           feedback=interview.feedback,
                           skills_to_improve=interview.skills_to_improve or [])


@router.patch("/{interview_id}/hide", status_code=204)
def hide(interview_id: int, candidate: ActiveCandidate, db: Database):
    interview = db.scalar(select(Interview).where(
        Interview.id == interview_id, Interview.candidate_id == candidate.id,
        Interview.active.is_(True), Interview.status == "completed",
        Interview.score.is_not(None)))
    if interview is None:
        raise HTTPException(404, "Entrevista no encontrada.")
    interview.active = False
    db.commit()
