from collections import deque
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import Request, Response
from openai import AuthenticationError, BadRequestError, RateLimitError
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    Candidate,
    CandidateSession,
    Interview,
    InterviewResponse,
    Vacancy,
    VacancyAnalysis,
)
from app.main import app
from app.modules.auth.router import db_session
from app.modules.vacancies import router as vacancy_router
from app.modules.vacancies.analysis import Finding, VacancyExtraction

API = "/api/v1/vacancies"
INPUT = {"title": "Junior React", "company": "Empresa X", "description":
         "Buscamos React, tres años de experiencia, guardias sin compensación y trabajo en equipo."}


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'vacancies.db'}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateSession.__table__, Vacancy.__table__, VacancyAnalysis.__table__,
        Interview.__table__, InterviewResponse.__table__,
    ])

    def session():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    vacancy_router._requests.clear()
    app.dependency_overrides[db_session] = session
    with TestClient(app, base_url="http://localhost:8000",
                    headers={"Origin": "http://localhost:5173"}) as http:
        yield http, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(http, email="ana@example.com"):
    return http.post("/api/v1/auth/register", json={
        "email": email, "first_name": "Ana", "last_name": "Pérez",
        "password": "ClaveSegura1!", "confirm_password": "ClaveSegura1!",
    })


@pytest.fixture
def model(monkeypatch):
    calls = []

    async def fake(title, company, description):
        calls.append((title, company, description))
        return VacancyExtraction(
            seniority="Junior (mencionado)", experience_required="3 años",
            technologies=["React"], required_skills=["Trabajo en equipo"],
            responsibilities=[], summary="Rol frontend con guardias.",
            inconsistencies=[Finding(title="Experiencia", explanation="Tres años para Junior.",
                                     relevance="alta", evidence="tres años de experiencia")],
            risk_signals=[Finding(title="Guardias", explanation="Falta compensación.",
                                  relevance="media", evidence="guardias sin compensación"),
                          Finding(title="Inventado", explanation="No está en el texto.",
                                  relevance="alta", evidence="salario impago")],
        )

    monkeypatch.setattr(vacancy_router, "analyze_offer", fake)
    return calls


def test_active_vacancy_quota_before_ai_and_admin_exemption(client, model):
    http, engine = client
    register(http, "cupos@example.com")
    with Session(engine) as db:
        owner = db.scalar(select(Candidate).where(Candidate.email == "cupos@example.com"))
        offers = [Vacancy(candidate_id=owner.id, title=f"Oferta {i}", description="Oferta")
                  for i in range(20)]
        db.add_all(offers)
        db.flush()
        db.add_all([VacancyAnalysis(vacancy_id=offer.id) for offer in offers])
        db.commit()
        hidden_id = db.scalar(select(Vacancy.id).where(Vacancy.candidate_id == owner.id))
    blocked = http.post(f"{API}/analyze", json=INPUT)
    assert blocked.status_code == 409
    assert "20 vacantes" in blocked.json()["detail"]
    assert model == []
    assert http.patch(f"{API}/{hidden_id}/hide").status_code == 204
    assert http.post(f"{API}/analyze", json=INPUT).status_code == 200
    with Session(engine) as db:
        owner = db.scalar(select(Candidate).where(Candidate.email == "cupos@example.com"))
        owner.admin = True
        db.commit()
    assert http.post(f"{API}/analyze", json=INPUT).status_code == 200


def test_public_ephemeral_and_authenticated_history(client, model):
    http, engine = client
    public = http.post(f"{API}/analyze", json=INPUT)
    assert public.status_code == 200
    assert public.json()["id"] is None
    assert public.json()["risk_percentage"] == 45
    assert len(public.json()["risk_signals"]) == 1
    assert model == [(INPUT["title"], INPUT["company"], INPUT["description"])]
    with Session(engine) as db:
        assert db.scalar(select(Vacancy)) is None
    assert http.get(API).status_code == 401

    register(http)
    saved = http.post(f"{API}/analyze", json=INPUT)
    assert saved.status_code == 200
    vacancy_id = saved.json()["id"]
    assert isinstance(vacancy_id, int)
    assert http.get(API).json()[0]["id"] == vacancy_id
    assert http.get(f"{API}/{vacancy_id}").json() == saved.json()
    with Session(engine) as db:
        assert db.scalar(select(VacancyAnalysis)).responsibilities == []
    register(http, "otra@example.com")
    assert http.get(API).json() == []
    assert http.get(f"{API}/{vacancy_id}").status_code == 404


def test_hiding_vacancy_requires_owner_and_preserves_interview(client, model):
    http, engine = client
    assert http.patch(f"{API}/1/hide").status_code == 401
    register(http)
    vacancy_id = http.post(f"{API}/analyze", json=INPUT).json()["id"]
    with Session(engine) as db:
        vacancy = db.get(Vacancy, vacancy_id)
        interview = Interview(candidate_id=vacancy.candidate_id, vacancy_id=vacancy_id,
                              status="completed", score=78, feedback="Buen resultado.")
        db.add(interview)
        db.flush()
        interview_id = interview.id
        db.add(InterviewResponse(interview_id=interview_id, question="¿React?", position=1))
        db.commit()

    register(http, "otra@example.com")
    assert http.patch(f"{API}/{vacancy_id}/hide").status_code == 404
    assert http.get(API).json() == []

    assert http.post("/api/v1/auth/login", json={
        "email": "ana@example.com", "password": "ClaveSegura1!",
    }).status_code == 200
    assert len(http.get(API).json()) == 1
    assert http.patch(f"{API}/{vacancy_id}/hide").status_code == 204
    assert http.get(API).json() == []
    assert http.get(f"{API}/{vacancy_id}").status_code == 404
    assert http.patch(f"{API}/{vacancy_id}/hide").status_code == 404
    with Session(engine) as db:
        assert db.get(Vacancy, vacancy_id).active is False
        assert db.scalar(select(VacancyAnalysis).where(VacancyAnalysis.vacancy_id == vacancy_id)) is not None
        assert db.get(Interview, interview_id).vacancy_id == vacancy_id
        assert db.scalar(select(InterviewResponse).where(
            InterviewResponse.interview_id == interview_id)) is not None


def test_validation_missing_key_provider_failure_and_limits(client, model, monkeypatch):
    http, _ = client
    assert http.post(f"{API}/analyze", json={**INPUT, "description": "   "}).status_code == 422
    assert http.post(f"{API}/analyze", json={**INPUT, "description": "x" * 12001}).status_code == 422
    assert http.post(f"{API}/analyze", json=INPUT, headers={"Origin": "https://otro.example"}).status_code == 403
    monkeypatch.setattr(settings, "openai_api_key", None)
    assert http.post(f"{API}/analyze", json=INPUT).status_code == 503
    assert model == []
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def failure(*_args):
        raise RuntimeError("secret-provider-error")

    monkeypatch.setattr(vacancy_router, "analyze_offer", failure)
    response = http.post(f"{API}/analyze", json=INPUT)
    assert response.status_code == 502
    assert "secret-provider-error" not in response.text
    vacancy_router._requests["ip:testclient"] = deque([vacancy_router.monotonic()] * 10)
    assert http.post(f"{API}/analyze", json=INPUT).status_code == 429


@pytest.mark.parametrize(("error", "detail"), [
    (RateLimitError("Sin saldo", response=Response(429, request=Request("POST", "https://api.openai.com/v1/chat/completions")),
                    body={"code": "credit_balance_exhausted"}),
     "no tiene créditos disponibles"),
    (RateLimitError("Demasiadas solicitudes", response=Response(429, request=Request("POST", "https://api.openai.com/v1/chat/completions")),
                    body={"code": "rate_limit_exceeded"}),
     "límite de solicitudes"),
    (AuthenticationError("Clave inválida", response=Response(401, request=Request("POST", "https://api.openai.com/v1/chat/completions")),
                         body={"code": "invalid_api_key"}),
     "clave de OpenAI configurada no es válida"),
])
def test_provider_configuration_errors_have_actionable_safe_messages(client, monkeypatch, error, detail):
    http, _ = client

    async def failure(*_args):
        raise error

    monkeypatch.setattr(vacancy_router, "analyze_offer", failure)
    response = http.post(f"{API}/analyze", json=INPUT)
    assert response.status_code == 503
    assert detail in response.json()["detail"]
    assert str(error) not in response.text


def test_unsupported_model_parameter_returns_safe_actionable_error(client, monkeypatch):
    http, _ = client
    error = BadRequestError(
        "secret-provider-response", response=Response(
            400, request=Request("POST", "https://api.openai.com/v1/chat/completions")),
        body={"param": "temperature", "code": "unsupported_value"},
    )

    async def failure(*_args):
        raise error

    monkeypatch.setattr(vacancy_router, "analyze_offer", failure)
    response = http.post(f"{API}/analyze", json=INPUT)
    assert response.status_code == 503
    assert "parámetros" in response.json()["detail"]
    assert "secret-provider-response" not in response.text


def test_extraction_rejects_values_that_do_not_fit_database():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VacancyExtraction(
            seniority="x" * 51, experience_required="", technologies=[], required_skills=[],
            responsibilities=[], summary="", inconsistencies=[], risk_signals=[],
        )
    with pytest.raises(ValidationError):
        Finding(title="Alerta", explanation="Explicación", relevance="alta", evidence="a")


def test_risk_score_does_not_count_the_same_evidence_twice(client, monkeypatch):
    http, _ = client

    async def duplicates(*_args):
        finding = Finding(title="Guardias", explanation="Condición a revisar.",
                          relevance="alta", evidence="guardias sin compensación")
        return VacancyExtraction(
            seniority="Junior", experience_required="", technologies=[], required_skills=[],
            responsibilities=[], summary="", inconsistencies=[finding, finding],
            risk_signals=[finding],
        )

    monkeypatch.setattr(vacancy_router, "analyze_offer", duplicates)
    result = http.post(f"{API}/analyze", json=INPUT)
    assert result.status_code == 200
    assert result.json()["risk_percentage"] == 30
    assert len(result.json()["inconsistencies"]) == 1
    assert result.json()["risk_signals"] == []


def test_vacancy_history_uses_private_keyset_pagination(client):
    http, engine = client
    register(http)
    with Session(engine) as db:
        candidate = db.scalar(select(Candidate).where(Candidate.email == "ana@example.com"))
        db.add_all([Vacancy(candidate_id=candidate.id, title=f"Oferta {i}",
                            description="Vacante de prueba",
                            created_at=datetime.now(UTC) - timedelta(minutes=i))
                    for i in range(24)])
        db.commit()
    first = http.get(f"{API}?limit=20").json()
    assert len(first) == 20
    anchor = first[-1]["id"]
    assert http.patch(f"{API}/{anchor}/hide").status_code == 204
    second = http.get(f"{API}?before={anchor}&limit=20").json()
    assert len(second) == 4
    assert {item["id"] for item in first}.isdisjoint(item["id"] for item in second)
    assert http.get(f"{API}?limit=101").status_code == 422
    register(http, "otra@example.com")
    assert http.get(f"{API}?before={anchor}").status_code == 404
