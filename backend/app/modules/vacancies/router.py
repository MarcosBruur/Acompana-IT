"""Análisis público efímero y análisis privados para candidatos autenticados."""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Candidate, CandidateSession, Vacancy, VacancyAnalysis
from app.modules.auth.router import COOKIE, Database, expired, token_digest
from app.modules.vacancies.analysis import Finding, analyze_offer

router = APIRouter(prefix="/vacancies", tags=["vacantes"])
logger = logging.getLogger(__name__)
WINDOW_SECONDS = 3600
_requests: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = asyncio.Lock()
_capacity = asyncio.Semaphore(3)


class VacancyInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=30, max_length=12000)

    @field_validator("title", "description")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Completá este campo.")
        return value

    @field_validator("company")
    @classmethod
    def optional_company(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class VacancyResult(BaseModel):
    id: int | None = None
    title: str
    company: str | None
    created_at: datetime | None = None
    seniority: str
    experience_required: str
    technologies: list[str]
    required_skills: list[str]
    responsibilities: list[str]
    summary: str
    inconsistencies: list[Finding]
    risk_signals: list[Finding]
    risk_percentage: int


class VacancySummary(BaseModel):
    id: int
    title: str
    company: str | None
    created_at: datetime
    risk_percentage: int | None


def optional_candidate(request: Request, db: Database) -> Candidate | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    session = db.scalar(select(CandidateSession).where(
        CandidateSession.token_hash == token_digest(token)))
    if not session:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC) or expired(session.candidate):
        return None
    return session.candidate


OptionalCandidate = Annotated[Candidate | None, Depends(optional_candidate)]


async def check_limit(key: str, limit: int) -> None:
    async with _rate_lock:
        now = monotonic()
        times = _requests[key]
        while times and times[0] <= now - WINDOW_SECONDS:
            times.popleft()
        if len(times) >= limit:
            raise HTTPException(429, "Alcanzaste el límite de análisis por hora. Intentá más tarde.")
        times.append(now)


def supported_findings(findings: list[Finding], source: str) -> list[Finding]:
    normalized = " ".join(source.casefold().split())
    return [finding for finding in findings if " ".join(finding.evidence.casefold().split()) in normalized]


def as_result(vacancy: Vacancy, analysis: VacancyAnalysis) -> VacancyResult:
    return VacancyResult(
        id=vacancy.id, title=vacancy.title, company=vacancy.company,
        created_at=vacancy.created_at, seniority=analysis.seniority or "",
        experience_required=analysis.experience_required or "",
        technologies=analysis.technologies, required_skills=analysis.required_skills,
        responsibilities=analysis.responsibilities, summary=analysis.summary or "",
        inconsistencies=analysis.inconsistencies, risk_signals=analysis.risk_signals,
        risk_percentage=analysis.risk_percentage or 0,
    )


@router.post("/analyze", response_model=VacancyResult)
async def analyze(data: VacancyInput, request: Request, db: Database, candidate: OptionalCandidate):
    if not settings.openai_api_key:
        raise HTTPException(503, "El análisis con IA aún no está configurado. Configurá OPENAI_API_KEY.")
    key = f"user:{candidate.id}" if candidate else f"ip:{request.client.host if request.client else 'unknown'}"
    await check_limit(key, 30 if candidate else 10)
    if _capacity.locked():
        raise HTTPException(429, "El servicio está ocupado. Volvé a intentarlo en unos momentos.")
    await _capacity.acquire()
    try:
        try:
            extraction = await analyze_offer(data.title, data.company, data.description)
        except RateLimitError as exc:
            logger.warning("OpenAI rechazó el análisis: tipo=%s estado=%s cuota_agotada=%s",
                           type(exc).__name__, exc.status_code,
                           exc.code == "credit_balance_exhausted")
            if exc.code == "credit_balance_exhausted":
                raise HTTPException(503, "La cuenta de OpenAI no tiene créditos disponibles. "
                                    "Revisá la facturación del proyecto asociado a OPENAI_API_KEY.") from None
            raise HTTPException(503, "OpenAI alcanzó su límite de solicitudes. "
                                "Volvé a intentarlo más tarde.") from None
        except AuthenticationError as exc:
            logger.warning("OpenAI rechazó la clave configurada: tipo=%s estado=%s",
                           type(exc).__name__, exc.status_code)
            raise HTTPException(503, "La clave de OpenAI configurada no es válida. "
                                "Revisá OPENAI_API_KEY en el backend.") from None
        except Exception as exc:  # noqa: BLE001 — no filtrar errores/datos del proveedor al cliente.
            logger.warning("Falló el análisis de OpenAI: tipo=%s estado=%s",
                           type(exc).__name__, getattr(exc, "status_code", None))
            raise HTTPException(502, "No se pudo analizar la oferta en este momento. Intentá de nuevo.") from None
    finally:
        _capacity.release()

    source = f"{data.title} {data.company or ''} {data.description}"
    inconsistencies = supported_findings(extraction.inconsistencies, source)
    signals = supported_findings(extraction.risk_signals, source)
    # Indicador explicable sobre alertas respaldadas por texto, no compatibilidad con un CV.
    weights = {"alta": 30, "media": 15, "baja": 5}
    percentage = min(100, sum(weights[item.relevance] for item in inconsistencies + signals))
    result = VacancyResult(
        title=data.title, company=data.company, **extraction.model_dump(exclude={"inconsistencies", "risk_signals"}),
        inconsistencies=inconsistencies, risk_signals=signals, risk_percentage=percentage,
    )
    if candidate:
        vacancy = Vacancy(candidate_id=candidate.id, title=data.title,
                          company=data.company, description=data.description)
        db.add(vacancy)
        db.flush()
        db.add(VacancyAnalysis(
            vacancy_id=vacancy.id, seniority=result.seniority or None,
            experience_required=result.experience_required or None,
            technologies=result.technologies, required_skills=result.required_skills,
            responsibilities=result.responsibilities,
            inconsistencies=[item.model_dump() for item in inconsistencies],
            risk_signals=[item.model_dump() for item in signals],
            risk_percentage=percentage, summary=result.summary,
        ))
        db.commit()
        db.refresh(vacancy)
        result.id = vacancy.id
        result.created_at = vacancy.created_at
    return result


@router.get("", response_model=list[VacancySummary])
def history(candidate: OptionalCandidate, db: Database):
    if not candidate:
        raise HTTPException(401, "Iniciá sesión para consultar tus análisis.")
    rows = db.scalars(select(Vacancy).where(Vacancy.candidate_id == candidate.id)
                      .order_by(Vacancy.created_at.desc(), Vacancy.id.desc()).limit(30)).all()
    return [VacancySummary(id=row.id, title=row.title, company=row.company,
                           created_at=row.created_at,
                           risk_percentage=row.analysis.risk_percentage if row.analysis else None)
            for row in rows]


@router.get("/{vacancy_id}", response_model=VacancyResult)
def get_analysis(vacancy_id: int, candidate: OptionalCandidate, db: Database):
    if not candidate:
        raise HTTPException(401, "Iniciá sesión para consultar tus análisis.")
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id,
                                             Vacancy.candidate_id == candidate.id))
    if not vacancy or not vacancy.analysis:
        raise HTTPException(404, "Análisis no encontrado.")
    return as_result(vacancy, vacancy.analysis)
