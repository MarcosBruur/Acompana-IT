"""Análisis público efímero y análisis privados para candidatos autenticados."""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_, select

from app.core.config import settings
from app.core.llm import invalid_request_detail
from app.core.quotas import check_vacancy_quota
from app.core.rate_limit import prune_buckets, shared_window
from app.db.models import Candidate, CandidateSession, Vacancy, VacancyAnalysis
from app.modules.auth.router import COOKIE, Database, expired, token_digest
from app.modules.vacancies.analysis import Finding, analyze_offer

router = APIRouter(prefix="/vacancies", tags=["vacantes"])
logger = logging.getLogger(__name__)
WINDOW_SECONDS = 3600
_requests: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = asyncio.Lock()
_capacity = asyncio.Semaphore(3)
_last_cleanup = 0.0
_shared_limit = shared_window()


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
    if expires_at <= datetime.now(UTC) or not session.candidate.active or expired(session.candidate):
        return None
    return session.candidate


OptionalCandidate = Annotated[Candidate | None, Depends(optional_candidate)]


async def check_limit(key: str, limit: int) -> None:
    global _last_cleanup
    if _shared_limit is not None:
        if not _shared_limit.check(f"vacancy:{key}", limit):
            raise HTTPException(429, "Alcanzaste el límite de análisis por hora. Intentá más tarde.")
        return
    async with _rate_lock:
        now = monotonic()
        if now - _last_cleanup >= 60:
            prune_buckets(_requests, now, WINDOW_SECONDS)
            _last_cleanup = now
        if key not in _requests and len(_requests) >= 30000:
            raise HTTPException(429, "El servicio está ocupado. Volvé a intentarlo más tarde.")
        times = _requests[key]
        while times and times[0] <= now - WINDOW_SECONDS:
            times.popleft()
        if len(times) >= limit:
            raise HTTPException(429, "Alcanzaste el límite de análisis por hora. Intentá más tarde.")
        times.append(now)


async def refund_limit(key: str) -> None:
    if _shared_limit is not None:
        _shared_limit.refund(f"vacancy:{key}")
        return
    async with _rate_lock:
        times = _requests.get(key)
        if times:
            times.pop()
            if not times:
                del _requests[key]


def supported_findings(findings: list[Finding], source: str) -> list[Finding]:
    normalized = " ".join(source.casefold().split())
    seen: set[str] = set()
    supported: list[Finding] = []
    for finding in findings:
        evidence = " ".join(finding.evidence.casefold().split())
        if evidence in normalized and evidence not in seen:
            seen.add(evidence)
            supported.append(finding)
    return supported


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
    candidate_id = candidate.id if candidate else None
    if candidate:
        check_vacancy_quota(db, candidate)
    await check_limit(key, 30 if candidate else 10)
    if _capacity.locked():
        await refund_limit(key)
        raise HTTPException(429, "El servicio está ocupado. Volvé a intentarlo en unos momentos.")
    # La autenticación ya se resolvió; no retener una transacción durante la espera externa.
    db.rollback()
    await _capacity.acquire()
    try:
        try:
            extraction = await analyze_offer(data.title, data.company, data.description)
        except RateLimitError as exc:
            await refund_limit(key)
            logger.warning("OpenAI rechazó el análisis: tipo=%s estado=%s cuota_agotada=%s",
                           type(exc).__name__, exc.status_code,
                           exc.code == "credit_balance_exhausted")
            if exc.code == "credit_balance_exhausted":
                raise HTTPException(503, "La cuenta de OpenAI no tiene créditos disponibles. "
                                    "Revisá la facturación del proyecto asociado a OPENAI_API_KEY.") from None
            raise HTTPException(503, "OpenAI alcanzó su límite de solicitudes. "
                                "Volvé a intentarlo más tarde.") from None
        except AuthenticationError as exc:
            await refund_limit(key)
            logger.warning("OpenAI rechazó la clave configurada: tipo=%s estado=%s",
                           type(exc).__name__, exc.status_code)
            raise HTTPException(503, "La clave de OpenAI configurada no es válida. "
                                "Revisá OPENAI_API_KEY en el backend.") from None
        except Exception as exc:  # noqa: BLE001 — no filtrar errores/datos del proveedor al cliente.
            await refund_limit(key)
            logger.warning("Falló el análisis de OpenAI: tipo=%s estado=%s",
                           type(exc).__name__, getattr(exc, "status_code", None))
            detail = invalid_request_detail(exc, "vacantes")
            if detail:
                raise HTTPException(503, detail) from None
            raise HTTPException(502, "No se pudo analizar la oferta en este momento. Intentá de nuevo.") from None
    finally:
        _capacity.release()

    source = f"{data.title} {data.company or ''} {data.description}"
    inconsistencies = supported_findings(extraction.inconsistencies, source)
    signals = supported_findings(extraction.risk_signals, source)
    # Un mismo fragmento no suma dos veces aunque se clasifique en ambas listas.
    used = {" ".join(item.evidence.casefold().split()) for item in inconsistencies}
    signals = [item for item in signals if " ".join(item.evidence.casefold().split()) not in used]
    # Indicador explicable sobre alertas respaldadas por texto, no compatibilidad con un CV.
    weights = {"alta": 30, "media": 15, "baja": 5}
    percentage = min(100, sum(weights[item.relevance] for item in inconsistencies + signals))
    result = VacancyResult(
        title=data.title, company=data.company, **extraction.model_dump(exclude={"inconsistencies", "risk_signals"}),
        inconsistencies=inconsistencies, risk_signals=signals, risk_percentage=percentage,
    )
    if candidate_id is not None:
        owner = db.scalar(select(Candidate).where(Candidate.id == candidate_id,
                                                  Candidate.active.is_(True))
                          .with_for_update().execution_options(populate_existing=True))
        if owner is None:
            raise HTTPException(401, "Iniciá sesión para guardar el análisis.")
        check_vacancy_quota(db, owner)
        vacancy = Vacancy(candidate_id=candidate_id, title=data.title,
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
def history(candidate: OptionalCandidate, db: Database,
            limit: int = Query(default=20, ge=1, le=100),
            before: int | None = Query(default=None, gt=0)):
    if not candidate:
        raise HTTPException(401, "Iniciá sesión para consultar tus análisis.")
    query = (select(Vacancy, VacancyAnalysis.risk_percentage)
             .outerjoin(VacancyAnalysis, VacancyAnalysis.vacancy_id == Vacancy.id)
             .where(Vacancy.candidate_id == candidate.id, Vacancy.active.is_(True)))
    if before is not None:
        anchor = db.scalar(select(Vacancy).where(Vacancy.id == before,
                                                 Vacancy.candidate_id == candidate.id))
        if anchor is None:
            raise HTTPException(404, "Vacante no encontrada.")
        query = query.where(or_(Vacancy.created_at < anchor.created_at,
                                and_(Vacancy.created_at == anchor.created_at,
                                     Vacancy.id < anchor.id)))
    rows = db.execute(query.order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
                      .limit(limit)).all()
    return [VacancySummary(id=row.id, title=row.title, company=row.company,
                           created_at=row.created_at, risk_percentage=risk)
            for row, risk in rows]


@router.get("/{vacancy_id}", response_model=VacancyResult)
def get_analysis(vacancy_id: int, candidate: OptionalCandidate, db: Database):
    if not candidate:
        raise HTTPException(401, "Iniciá sesión para consultar tus análisis.")
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id,
                                             Vacancy.candidate_id == candidate.id,
                                             Vacancy.active.is_(True)))
    if not vacancy or not vacancy.analysis:
        raise HTTPException(404, "Análisis no encontrado.")
    return as_result(vacancy, vacancy.analysis)


@router.patch("/{vacancy_id}/hide", status_code=204)
def hide_vacancy(vacancy_id: int, candidate: OptionalCandidate, db: Database):
    if not candidate:
        raise HTTPException(401, "Iniciá sesión para gestionar tus vacantes.")
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id,
                                             Vacancy.candidate_id == candidate.id,
                                             Vacancy.active.is_(True)))
    if not vacancy:
        raise HTTPException(404, "Vacante no encontrada.")
    vacancy.active = False
    db.commit()
