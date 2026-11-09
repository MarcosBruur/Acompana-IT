import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import MockTransport, Request, Response
from langchain_core.runnables import RunnableLambda
from openai import BadRequestError
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Candidate,
    CandidateSession,
    Interview,
    InterviewResponse,
    Resume,
    Vacancy,
    VacancyAnalysis,
)
from app.main import app
from app.modules.auth.router import db_session
from app.modules.interviews import router as interview_router
from app.modules.interviews import simulation
from app.modules.interviews.simulation import Evaluation, Question, QuestionSet

API = "/api/v1/interviews"


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "first_name": "Ana", "last_name": "Pérez",
        "password": "ClaveSegura1!", "confirm_password": "ClaveSegura1!",
    })
    assert response.status_code == 201


def create_vacancy(engine, email):
    with Session(engine) as db:
        candidate = db.scalar(select(Candidate).where(Candidate.email == email))
        vacancy = Vacancy(candidate_id=candidate.id, title="Python Jr",
                          description="Desarrollo en Python, SQL y resolución de problemas.")
        db.add(vacancy)
        db.flush()
        db.add(VacancyAnalysis(vacancy_id=vacancy.id))
        db.commit()
        return vacancy.id


def questions(mode):
    return QuestionSet(questions=[Question(
        topic="Python", question=f"¿Cómo resolvés el problema {i} con Python?",
        options=["Con Python", "Con SQL", "Con HTML", "Con CSS"] if mode == "multiple_choice" else [],
        correct_index=0 if mode == "multiple_choice" else None,
        reference_answer="Se resuelve con una función de Python y sus pruebas.",
    ) for i in range(12 if mode == "multiple_choice" else 10)])


def test_multiple_choice_private_questions_early_finish_and_hidden_vacancy(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'choice.db'}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateSession.__table__, Resume.__table__, Vacancy.__table__,
        VacancyAnalysis.__table__, Interview.__table__, InterviewResponse.__table__,
    ])

    def session():
        with Session(engine) as db:
            yield db

    async def generate(_title, _description, _resume, mode):
        return questions(mode)

    monkeypatch.setattr(interview_router.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(interview_router.settings, "openai_voice_model", "gpt-realtime-2.1-mini")
    monkeypatch.setattr(interview_router.settings, "openai_voice", "marin")
    monkeypatch.setattr(interview_router, "generate_questions", generate)
    app.dependency_overrides[db_session] = session
    try:
        with TestClient(app, base_url="http://localhost:8000",
                        headers={"Origin": "http://localhost:5173"}) as client:
            register(client, "ana@example.com")
            vacancy_id = create_vacancy(engine, "ana@example.com")
            created = client.post(API, json={"vacancy_id": vacancy_id, "mode": "multiple_choice"})
            assert created.status_code == 201, created.text
            initial = created.json()
            interview_id = initial["id"]
            assert len(initial["questions"]) == 12
            assert all(item["correct_index"] is None and item["explanation"] is None
                       for item in initial["questions"])
            question_id = initial["questions"][0]["id"]
            assert client.get(f"{API}/active").json()["id"] == interview_id
            assert client.post(f"{API}/{interview_id}/voice-token").status_code == 409
            assert client.put(f"{API}/{interview_id}/questions/{question_id}",
                              json={"selected_index": 0}).json()["questions"][0]["answer"] == "0"
            assert client.put(f"{API}/{interview_id}/questions/{question_id}",
                              json={"selected_index": 8}).status_code == 422
            register(client, "otra@example.com")
            assert client.get(f"{API}/{interview_id}/session").status_code == 404
            assert client.post(f"{API}/{interview_id}/voice-token").status_code == 404
            assert client.post(f"{API}/{interview_id}/finish").status_code == 404
            assert client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation"}).status_code == 404
            client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "ClaveSegura1!"})
            final = client.post(f"{API}/{interview_id}/finish")
            assert final.status_code == 200, final.text
            assert final.json()["correct_count"] == 1
            assert final.json()["incorrect_count"] == 11
            assert final.json()["unanswered_count"] == 11
            assert final.json()["score"] == 8
            assert final.json()["questions"][0]["correct_index"] == 0
            assert final.json()["resources"][0]["url"].startswith("https://")
            assert client.get(f"{API}/active").json() is None
            assert client.post(f"{API}/{interview_id}/finish").status_code == 409
            assert client.patch(f"/api/v1/vacancies/{vacancy_id}/hide").status_code == 204
            assert client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation"}).status_code == 404
            assert client.get(f"{API}/{interview_id}").status_code == 200
            with Session(engine) as db:
                assert db.scalar(select(InterviewResponse).where(
                    InterviewResponse.interview_id == interview_id,
                    InterviewResponse.position == 2)).answer is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_conversation_correction_resume_and_cancel(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'conversation.db'}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateSession.__table__, Resume.__table__, Vacancy.__table__,
        VacancyAnalysis.__table__, Interview.__table__, InterviewResponse.__table__,
    ])

    def session():
        with Session(engine) as db:
            yield db

    received_resume = []

    async def generate(_title, _description, _resume, mode):
        received_resume.append(_resume)
        return questions(mode)

    evaluation_contexts = []

    async def evaluate(_question, _reference, _answer, **context):
        evaluation_contexts.append(context)
        return Evaluation(verdict="incorrecta", explanation="No es correcto; Python usa funciones y pruebas.")

    monkeypatch.setattr(interview_router.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(interview_router.settings, "openai_voice_model", "gpt-realtime-2.1-mini")
    monkeypatch.setattr(interview_router.settings, "openai_voice", "marin")
    monkeypatch.setattr(interview_router, "generate_questions", generate)
    monkeypatch.setattr(interview_router, "evaluate_answer", evaluate)
    app.dependency_overrides[db_session] = session
    try:
        with TestClient(app, base_url="http://localhost:8000",
                        headers={"Origin": "http://localhost:5173"}) as client:
            register(client, "ana@example.com")
            vacancy_id = create_vacancy(engine, "ana@example.com")
            assert client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation",
                                          "use_resume": True}).status_code == 422
            async def bad_request(*_args):
                raise BadRequestError(
                    "private-prompt-or-key", response=Response(
                        400, request=Request("POST", "https://api.openai.com/v1/chat/completions")),
                    body={"param": "temperature"},
                )

            monkeypatch.setattr(interview_router, "generate_questions", bad_request)
            failure = client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation"})
            assert failure.status_code == 503
            assert "private-prompt-or-key" not in failure.text
            monkeypatch.setattr(interview_router, "generate_questions", generate)
            started = client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation"}).json()
            interview_id, first_id, second_id = started["id"], started["questions"][0]["id"], started["questions"][1]["id"]
            requests = []
            original_client = httpx.AsyncClient

            def token_request(request):
                requests.append(request)
                assert request.url.path == "/v1/realtime/client_secrets"
                payload = json.loads(request.content)
                assert payload["session"]["model"] == "gpt-realtime-2.1-mini"
                assert payload["session"]["audio"]["output"]["voice"] == "marin"
                assert "CV privado" not in request.content.decode()
                return Response(200, json={"value": "ephemeral-test"})

            monkeypatch.setattr(interview_router.httpx, "AsyncClient", lambda **kwargs: original_client(
                transport=MockTransport(token_request), **kwargs))
            minted = client.post(f"{API}/{interview_id}/voice-token")
            assert minted.status_code == 200 and minted.json() == {"value": "ephemeral-test"}
            assert minted.headers["cache-control"] == "no-store"
            assert len(requests) == 1
            monkeypatch.setattr(interview_router.settings, "openai_voice", "voz-invalida")
            assert client.post(f"{API}/{interview_id}/voice-token").status_code == 503
            assert len(requests) == 1
            monkeypatch.setattr(interview_router.settings, "openai_voice", "marin")
            monkeypatch.setattr(interview_router.httpx, "AsyncClient", lambda **kwargs: original_client(
                transport=MockTransport(lambda _request: Response(400, json={
                    "error": {"message": "private-prompt-or-key"}})), **kwargs))
            unavailable = client.post(f"{API}/{interview_id}/voice-token")
            assert unavailable.status_code == 503
            assert "private-prompt-or-key" not in unavailable.text
            assert client.post(f"{API}/{interview_id}/questions/{second_id}/answer",
                               json={"answer": "Cualquier cosa"}).status_code == 409
            reply = client.post(f"{API}/{interview_id}/questions/{first_id}/answer",
                                json={"answer": "No sé."})
            assert reply.status_code == 200
            assert reply.json()["questions"][0]["verdict"] == "incorrecta"
            assert "No es correcto" in reply.json()["questions"][0]["explanation"]
            assert evaluation_contexts[0]["vacancy_title"] == "Python Jr"
            assert "Python, SQL" in evaluation_contexts[0]["vacancy_description"]
            assert evaluation_contexts[0]["topic"] == "Python"
            assert client.post(f"{API}/{interview_id}/questions/{first_id}/answer",
                               json={"answer": "Otra respuesta"}).status_code == 409
            assert client.get(f"{API}/{interview_id}/session").json()["questions"][0]["answer"] == "No sé."
            second = client.post(f"{API}/{interview_id}/questions/{second_id}/answer",
                                 json={"answer": "Usaría una función con pruebas."})
            assert second.status_code == 200
            assert "No sé." in evaluation_contexts[1]["previous"]
            assert "Python Jr" == evaluation_contexts[1]["vacancy_title"]
            assert client.post(f"{API}/{interview_id}/cancel").status_code == 204
            assert client.post(f"{API}/{interview_id}/voice-token").status_code == 409
            assert client.get(API).json() == []
            assert client.get(f"{API}/{interview_id}").status_code == 404
            assert client.post(f"{API}/{interview_id}/finish").status_code == 409
            with Session(engine) as db:
                candidate = db.scalar(select(Candidate).where(Candidate.email == "ana@example.com"))
                resume = Resume(candidate_id=candidate.id, filename="cv.pdf",
                                storage_key="files/cv.pdf", is_primary=True)
                db.add(resume)
                db.commit()
                resume_id = resume.id
            monkeypatch.setattr(interview_router, "resume_text", lambda _resume: "CV privado con texto")
            with_cv = client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation",
                                             "use_resume": True})
            assert with_cv.status_code == 201, with_cv.text
            assert received_resume[-1] == "CV privado con texto"
            assert with_cv.json()["using_resume"] is True
            assert client.post(f"{API}/{with_cv.json()['id']}/cancel").status_code == 204
            assert client.patch(f"/api/v1/profile/resumes/{resume_id}/hide").status_code == 204
            assert client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation",
                                          "use_resume": True}).status_code == 422
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_conversation_full_and_partial_answers_score_without_model_reply(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'grading.db'}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateSession.__table__, Resume.__table__, Vacancy.__table__,
        VacancyAnalysis.__table__, Interview.__table__, InterviewResponse.__table__,
    ])

    def session():
        with Session(engine) as db:
            yield db

    async def generate(_title, _description, _resume, mode):
        return questions(mode)

    async def evaluate(_question, _reference, answer, **_context):
        if answer == "Completa":
            # Aunque el proveedor devuelva texto, no debe almacenarse ni revelarse.
            return Evaluation(verdict="correcta", explanation="Respuesta modelo no solicitada.")
        if answer == "Parcial":
            return Evaluation(verdict="parcial", explanation="Faltó explicar cómo probarías la función.")
        return Evaluation(verdict="incorrecta", explanation="La solución requiere una función de Python.")

    monkeypatch.setattr(interview_router.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(interview_router, "generate_questions", generate)
    monkeypatch.setattr(interview_router, "evaluate_answer", evaluate)
    app.dependency_overrides[db_session] = session
    try:
        with TestClient(app, base_url="http://localhost:8000",
                        headers={"Origin": "http://localhost:5173"}) as client:
            register(client, "completa@example.com")
            vacancy_id = create_vacancy(engine, "completa@example.com")
            started = client.post(API, json={"vacancy_id": vacancy_id, "mode": "conversation"}).json()
            interview_id = started["id"]
            ids = [item["id"] for item in started["questions"]]
            full = client.post(f"{API}/{interview_id}/questions/{ids[0]}/answer",
                               json={"answer": "Completa"}).json()["questions"][0]
            assert full["verdict"] == "correcta"
            assert full["explanation"] is None
            partial = client.post(f"{API}/{interview_id}/questions/{ids[1]}/answer",
                                  json={"answer": "Parcial"}).json()["questions"][1]
            assert partial["verdict"] == "parcial"
            assert "Faltó" in partial["explanation"]
            incorrect = client.post(f"{API}/{interview_id}/questions/{ids[2]}/answer",
                                    json={"answer": "Equivocada"}).json()["questions"][2]
            assert incorrect["verdict"] == "incorrecta"
            with Session(engine) as db:
                db.get(InterviewResponse, ids[3]).reference_answer = "cursor.execute('SELECT id FROM usuarios')"
                db.commit()
            final = client.post(f"{API}/{interview_id}/finish").json()
            assert final["correct_count"] == 1
            assert final["partial_count"] == 1
            assert final["incorrect_count"] == 8  # Incluye las siete omitidas.
            assert final["unanswered_count"] == 7
            assert final["score"] == 15  # (1 + 0,5) / 10.
            assert final["questions"][0]["explanation"] is None
            assert "cursor.execute" not in final["questions"][3]["explanation"]
            assert not simulation.contains_literal_code(final["questions"][3]["explanation"])
            assert "medio punto" in final["feedback"]
            assert client.get(f"{API}/{interview_id}").json()["partial_count"] == 1
            with Session(engine) as db:
                assert db.get(InterviewResponse, ids[0]).explanation is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_resume_without_extractable_text_is_rejected(tmp_path, monkeypatch):
    pdf = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    with pdf.open("wb") as output:
        writer.write(output)
    monkeypatch.setattr(interview_router, "stored_file", lambda _key, _kind: pdf)
    resume = Resume(candidate_id=1, filename="cv.pdf", storage_key="files/scanned.pdf")
    with pytest.raises(HTTPException, match="texto extraíble"):
        interview_router.resume_text(resume)


def test_partial_answer_requires_specific_feedback():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Evaluation(verdict="parcial", explanation=None)
    with pytest.raises(ValidationError):
        Evaluation(verdict="incorrecta", explanation="  ")


@pytest.mark.parametrize(("explanation", "contains_code"), [
    ("En FastAPI usarías validación antes de guardar los datos en PostgreSQL.", False),
    ("Con React, los componentes comparten estado mediante hooks.", False),
    ("Podés usar `cursor.execute('SELECT id FROM usuarios')`.", True),
    ("SELECT id FROM usuarios para encontrar el registro.", True),
    ("Para resolverlo, llamá a validar_usuario(datos).", True),
    ("Revisá x = 1 antes de persistir.", True),
    ("Luego usá cursor.execute para continuar.", True),
    ("En JavaScript, Node.js permite montar un servidor.", False),
    ("```python\ndef validar(): pass\n```", True),
])
def test_spoken_correction_detects_only_literal_code(explanation, contains_code):
    assert simulation.contains_literal_code(explanation) is contains_code


def test_code_in_conversation_feedback_is_rephrased_once(monkeypatch):
    requested_schemas = []

    class FakeModel:
        def with_structured_output(self, schema, *, method, strict):
            assert method == "json_schema" and strict is True
            requested_schemas.append(schema)
            if schema is Evaluation:
                return RunnableLambda(lambda _prompt: {
                    "verdict": "parcial", "explanation": "Usá `cursor.execute('SELECT ...')`.",
                })
            return RunnableLambda(lambda _prompt: {
                "explanation": "En PostgreSQL, usá consultas parametrizadas para proteger los datos.",
            })

    monkeypatch.setattr(simulation, "model", lambda _tokens: FakeModel())
    result = asyncio.run(simulation.evaluate_answer(
        "¿Cómo evitás la inyección SQL?", "Consultas parametrizadas", "Escaparía comillas",
        vacancy_title="Backend Python", vacancy_description="Python y PostgreSQL",
        topic="Seguridad", previous="",
    ))
    assert result.verdict == "parcial"
    assert "consultas parametrizadas" in result.explanation
    assert not simulation.contains_literal_code(result.explanation)
    assert requested_schemas == [Evaluation, simulation.SpokenCorrection]


def test_persistent_code_in_feedback_is_not_returned(monkeypatch):
    class FakeModel:
        def with_structured_output(self, schema, *, method, strict):
            if schema is Evaluation:
                return RunnableLambda(lambda _prompt: {
                    "verdict": "incorrecta", "explanation": "Usá `print(datos)` para eso.",
                })
            return RunnableLambda(lambda _prompt: {"explanation": "Ejecutá `print(datos)` ahora."})

    monkeypatch.setattr(simulation, "model", lambda _tokens: FakeModel())
    with pytest.raises(ValueError, match="sin código literal"):
        asyncio.run(simulation.evaluate_answer(
            "¿Cómo evitarías ese error?", "Validación de datos", "No sé",
            vacancy_title="Backend Python", vacancy_description="Python y PostgreSQL",
            topic="Validación", previous="",
        ))
