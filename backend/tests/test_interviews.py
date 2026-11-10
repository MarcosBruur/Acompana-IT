from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Candidate, CandidateSession, Interview, InterviewResponse, Vacancy
from app.main import app
from app.modules.auth.router import db_session

API = "/api/v1/interviews"


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


def register(client: TestClient, email: str):
    return client.post("/api/v1/auth/register", json={
        "email": email, "first_name": "Ana", "last_name": "Pérez",
        "password": "ClaveSegura1!", "confirm_password": "ClaveSegura1!",
    })


def test_interview_history_details_and_hide(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'interviews.db'}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateSession.__table__, Vacancy.__table__, Interview.__table__,
        InterviewResponse.__table__,
    ])

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[db_session] = session
    try:
        with TestClient(app, base_url="http://localhost:8000",
                        headers={"Origin": "http://localhost:5173"}) as client:
            assert client.get(API).status_code == 401
            assert register(client, "ana@example.com").status_code == 201
            assert client.get(API).json() == []
            with Session(engine) as db:
                owner = db.scalar(select(Candidate).where(Candidate.email == "ana@example.com"))
                vacancy = Vacancy(candidate_id=owner.id, title="Desarrollo React", description="Oferta")
                db.add(vacancy)
                db.flush()
                finished = Interview(candidate_id=owner.id, vacancy_id=vacancy.id,
                                     status="completed", score=82, feedback="Buen razonamiento.",
                                     skills_to_improve=["Pruebas unitarias"])
                pending = Interview(candidate_id=owner.id, vacancy_id=vacancy.id,
                                    status="in_progress")
                db.add_all([finished, pending])
                db.flush()
                db.add(InterviewResponse(interview_id=finished.id, question="¿Qué es React?",
                                         answer="Una biblioteca.", position=1))
                finished_id, pending_id = finished.id, pending.id
                db.commit()

            entries = client.get(API).json()
            assert len(entries) == 1
            assert entries[0]["vacancy_title"] == "Desarrollo React"
            assert entries[0]["score"] == 82
            assert entries[0]["created_at"]
            assert client.get(f"{API}/{pending_id}").status_code == 404
            detail = client.get(f"{API}/{finished_id}").json()
            assert detail["feedback"] == "Buen razonamiento."
            assert detail["skills_to_improve"] == ["Pruebas unitarias"]

            assert register(client, "otra@example.com").status_code == 201
            assert client.get(API).json() == []
            assert client.get(f"{API}/{finished_id}").status_code == 404
            assert client.patch(f"{API}/{finished_id}/hide").status_code == 404

            assert client.post("/api/v1/auth/login", json={
                "email": "ana@example.com", "password": "ClaveSegura1!"}).status_code == 200
            assert client.patch(f"{API}/{finished_id}/hide").status_code == 204
            assert client.get(API).json() == []
            assert client.patch(f"{API}/{finished_id}/hide").status_code == 404
            # Ocultar no elimina el resultado ni las respuestas guardadas.
            assert client.get(f"{API}/{finished_id}").json()["score"] == 82
            with Session(engine) as db:
                assert db.get(Interview, finished_id).active is False
                assert db.scalar(select(InterviewResponse).where(
                    InterviewResponse.interview_id == finished_id)) is not None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_interview_history_keyset_pagination(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'interviews-page.db'}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__, CandidateSession.__table__,
                                             Vacancy.__table__, Interview.__table__])

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[db_session] = session
    try:
        with TestClient(app, base_url="http://localhost:8000",
                        headers={"Origin": "http://localhost:5173"}) as client:
            assert register(client, "ana@example.com").status_code == 201
            with Session(engine) as db:
                candidate = db.scalar(select(Candidate))
                vacancy = Vacancy(candidate_id=candidate.id, title="Python", description="Oferta")
                db.add(vacancy)
                db.flush()
                db.add_all([Interview(candidate_id=candidate.id, vacancy_id=vacancy.id,
                                      status="completed", score=60,
                                      created_at=datetime.now(UTC) - timedelta(minutes=i))
                            for i in range(22)])
                db.commit()
            first = client.get(API).json()
            assert len(first) == 20
            second = client.get(f"{API}?before={first[-1]['id']}").json()
            assert len(second) == 2
            assert {item["id"] for item in first}.isdisjoint(item["id"] for item in second)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
