"""Entrevistas privadas: preparación, respuestas, finalización e historial."""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from time import monotonic

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from openai import AuthenticationError, RateLimitError
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from websockets.asyncio.client import connect as realtime_connect
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.llm import invalid_request_detail
from app.core.pdf_processing import InvalidPdf, process_pdf
from app.core.quotas import check_interview_quota
from app.core.rate_limit import RateLimitUnavailable, prune_buckets, shared_window
from app.db.models import Candidate, CandidateSession, Interview, InterviewResponse, Resume, Vacancy
from app.modules.auth.router import (
    COOKIE,
    ActiveCandidate,
    Database,
    expired,
    token_digest,
)
from app.modules.interviews.simulation import (
    contains_literal_code,
    evaluate_answer,
    generate_questions,
    learning_resources,
)
from app.modules.profile.router import stored_file

router = APIRouter(prefix="/interviews", tags=["entrevistas"])
logger = logging.getLogger(__name__)
_capacity = asyncio.Semaphore(3)
_voice_attempts: dict[int, deque[float]] = defaultdict(deque)
_voice_lock = asyncio.Lock()
_voice_cleanup = 0.0
_shared_limit = shared_window()


async def refund_voice_attempt(candidate_id: int) -> None:
    if _shared_limit is not None:
        _shared_limit.refund(f"interview:voice:{candidate_id}")
        return
    async with _voice_lock:
        times = _voice_attempts.get(candidate_id)
        if times:
            times.pop()
            if not times:
                del _voice_attempts[candidate_id]


class InterviewSummary(BaseModel):
    id: int
    vacancy_title: str
    created_at: datetime
    score: int


class QuestionOutput(BaseModel):
    id: int
    position: int
    topic: str | None
    question: str
    options: list[str] | None
    answer: str | None
    verdict: str | None
    explanation: str | None
    correct_index: int | None = None


class InterviewSession(BaseModel):
    id: int
    vacancy_title: str
    mode: str
    status: str
    using_resume: bool
    questions: list[QuestionOutput]


class ResourceOutput(BaseModel):
    title: str
    url: str


class InterviewResult(InterviewSummary):
    feedback: str | None
    skills_to_improve: list[str]
    mode: str
    correct_count: int
    partial_count: int
    incorrect_count: int
    unanswered_count: int
    resources: list[ResourceOutput]
    questions: list[QuestionOutput]


class StartInput(BaseModel):
    vacancy_id: int = Field(gt=0)
    mode: str = Field(pattern="^(conversation|multiple_choice)$")
    use_resume: bool = False


class ChoiceInput(BaseModel):
    selected_index: int | None = Field(default=None, ge=0, le=3)


class AnswerInput(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


def voice_session_config() -> dict:
    return {"session": {
        "type": "realtime", "model": settings.openai_voice_model,
        "output_modalities": ["audio"], "max_output_tokens": 2000,
        "audio": {"input": {"turn_detection": None},
                  "output": {"voice": settings.openai_voice,
                             "format": {"type": "audio/pcm", "rate": 24000}}},
        "instructions": (
            "Leé en español rioplatense de Argentina, con acento argentino natural y sutil, "
            "sin exagerarlo ni cambiar de idioma. Usá entonación cálida, ritmo conversacional "
            "y pausas breves al cambiar de idea. Leé literalmente el texto recibido: no cambies "
            "palabras, agregues opiniones, respondas preguntas ni inventes correcciones."
        ),
    }}


def questions_for(interview: Interview, *, finished: bool = False) -> list[QuestionOutput]:
    return [QuestionOutput(
        id=item.id, position=item.position, topic=item.topic, question=item.question,
        options=item.options, answer=item.answer, verdict=item.verdict,
        explanation=item.explanation if finished or interview.mode == "conversation" else None,
        correct_index=item.correct_index if finished else None,
    ) for item in sorted(interview.responses, key=lambda item: item.position)]


def as_session(interview: Interview) -> InterviewSession:
    return InterviewSession(id=interview.id, vacancy_title=interview.vacancy.title,
                            mode=interview.mode, status=interview.status,
                            using_resume=interview.resume_id is not None,
                            questions=questions_for(interview))


def owned(interview_id: int, candidate_id: int, db: Database, *, lock: bool = False) -> Interview:
    query = select(Interview).where(Interview.id == interview_id,
                                    Interview.candidate_id == candidate_id)
    interview = db.scalar(query.with_for_update() if lock else query)
    if interview is None:
        raise HTTPException(404, "Entrevista no encontrada.")
    return interview


def ongoing(interview_id: int, candidate_id: int, db: Database, *, lock: bool = False) -> Interview:
    interview = owned(interview_id, candidate_id, db, lock=lock)
    if interview.status != "in_progress":
        raise HTTPException(409, "Esta entrevista ya terminó.")
    return interview


def resume_text(resume: Resume) -> str:
    try:
        with stored_file(resume.storage_key, "files").open("rb") as document:
            text = process_pdf(document.read(5 * 1024 * 1024 + 1), extract=True)
    except (OSError, InvalidPdf) as exc:
        raise HTTPException(422, "No se pudo leer el CV principal. Probá con otro PDF.") from exc
    if len(text) < 40:
        raise HTTPException(422, "El CV principal no tiene texto extraíble. Subí un PDF con texto seleccionable o iniciá sin CV.")
    return text


def provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AuthenticationError, RateLimitError)):
        return HTTPException(503, "El servicio de IA no está disponible en este momento. Intentá más tarde.")
    detail = invalid_request_detail(exc, "entrevistas")
    if detail:
        logger.warning("OpenAI rechazó la entrevista: tipo=%s estado=%s",
                       type(exc).__name__, getattr(exc, "status_code", None))
        return HTTPException(503, detail)
    return HTTPException(502, "No se pudo procesar la entrevista. Intentá de nuevo.")


@router.get("/active", response_model=InterviewSession | None)
def active_interview(candidate: ActiveCandidate, db: Database):
    interview = db.scalar(select(Interview).where(
        Interview.candidate_id == candidate.id, Interview.status == "in_progress")
        .order_by(Interview.created_at.desc(), Interview.id.desc()).limit(1))
    return as_session(interview) if interview else None


@router.post("", response_model=InterviewSession, status_code=201)
async def start(data: StartInput, candidate: ActiveCandidate, db: Database):
    candidate_id = candidate.id
    if not settings.openai_api_key:
        raise HTTPException(503, "La simulación con IA aún no está configurada. Configurá OPENAI_API_KEY.")
    vacancy = db.scalar(select(Vacancy).where(
        Vacancy.id == data.vacancy_id, Vacancy.candidate_id == candidate_id,
        Vacancy.active.is_(True)))
    if vacancy is None or vacancy.analysis is None:
        raise HTTPException(404, "Elegí una vacante analizada y activa de tu cuenta.")
    existing = db.scalar(select(Interview.id).where(
        Interview.candidate_id == candidate_id, Interview.status == "in_progress"))
    if existing is not None:
        raise HTTPException(409, "Ya tenés una entrevista en curso. Retomala o cancelala antes de iniciar otra.")
    check_interview_quota(db, candidate)
    resume = None
    text = ""
    if data.use_resume:
        resume = db.scalar(select(Resume).where(
            Resume.candidate_id == candidate_id, Resume.is_primary.is_(True),
            Resume.active.is_(True)))
        if resume is None:
            raise HTTPException(422, "Establecé un CV principal activo en tu perfil o iniciá sin CV.")
    if _capacity.locked():
        raise HTTPException(429, "El servicio está ocupado. Intentá en unos momentos.")
    title, description = vacancy.title, vacancy.description
    resume_id = resume.id if resume else None
    if resume:
        db.expunge(resume)
    db.rollback()
    if resume:
        text = await run_in_threadpool(resume_text, resume)
    await _capacity.acquire()
    try:
        try:
            generated = await generate_questions(title, description, text, data.mode)
        except Exception as exc:  # noqa: BLE001 — no exponer respuestas o contenido del proveedor.
            raise provider_error(exc) from None
    finally:
        _capacity.release()
    owner = db.scalar(select(Candidate).where(
        Candidate.id == candidate_id, Candidate.active.is_(True))
        .with_for_update().execution_options(populate_existing=True))
    if owner is None:
        raise HTTPException(401, "Iniciá sesión para continuar.")
    vacancy = db.scalar(select(Vacancy).where(
        Vacancy.id == data.vacancy_id, Vacancy.candidate_id == candidate_id,
        Vacancy.active.is_(True)))
    if vacancy is None or vacancy.analysis is None:
        raise HTTPException(404, "Elegí una vacante analizada y activa de tu cuenta.")
    if resume_id is not None and not db.scalar(select(Resume.id).where(
        Resume.id == resume_id, Resume.candidate_id == candidate_id,
        Resume.active.is_(True), Resume.is_primary.is_(True))):
        raise HTTPException(409, "Tu CV principal cambió durante la preparación. Intentá de nuevo.")
    if db.scalar(select(Interview.id).where(
        Interview.candidate_id == candidate_id, Interview.status == "in_progress")):
        raise HTTPException(409, "Ya tenés una entrevista en curso. Retomala antes de iniciar otra.")
    check_interview_quota(db, owner)
    interview = Interview(candidate_id=candidate_id, vacancy_id=vacancy.id,
                          resume_id=resume_id, mode=data.mode,
                          status="in_progress")
    try:
        db.add(interview)
        db.flush()
        for position, item in enumerate(generated.questions, start=1):
            db.add(InterviewResponse(interview_id=interview.id, position=position,
                                     question=item.question, topic=item.topic, options=item.options or None,
                                     correct_index=item.correct_index,
                                     reference_answer=item.reference_answer))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya tenés una entrevista en curso. Retomala antes de iniciar otra.") from None
    db.refresh(interview)
    return as_session(interview)


@router.get("/{interview_id}/session", response_model=InterviewSession)
def session(interview_id: int, candidate: ActiveCandidate, db: Database):
    return as_session(ongoing(interview_id, candidate.id, db))


def approved_voice_text(interview: Interview, keys: object) -> str:
    """Solo usar preguntas/correcciones persistidas; nunca aceptar texto libre del cliente."""
    if not isinstance(keys, list) or not 1 <= len(keys) <= 3:
        raise ValueError("Fragmentos no válidos")
    questions = {item.id: item for item in interview.responses}
    by_position = {item.position: item for item in interview.responses}
    parts: list[str] = []
    for key in keys:
        if not isinstance(key, str) or len(key) > 32 or "-" not in key:
            raise ValueError("Fragmento no válido")
        kind, _, raw_id = key.partition("-")
        if not raw_id.isdecimal() or int(raw_id) not in questions:
            raise ValueError("Pregunta no encontrada")
        question = questions[int(raw_id)]
        if kind == "q":
            parts.append(question.question)
        elif kind == "e" and question.verdict in {"parcial", "incorrecta"} and question.explanation:
            if contains_literal_code(question.explanation):
                raise ValueError("Corrección no apta para voz")
            parts.append(question.explanation)
        elif kind == "c" and question.position > 1:
            previous = by_position.get(question.position - 1)
            if previous is None or previous.verdict is None:
                raise ValueError("Transición no disponible")
            parts.append("Bien, sigamos con la siguiente pregunta." if previous.verdict == "correcta"
                         else "Pasemos a la siguiente pregunta.")
        elif kind == "end" and all(item.verdict is not None for item in interview.responses):
            parts.append("Terminaste las preguntas. Finalizá para ver tus resultados.")
        else:
            raise ValueError("Fragmento no permitido")
    text = " ".join(parts)
    if not text or len(text) > 1400:
        raise ValueError("Fragmentos demasiado largos")
    return text


@router.websocket("/{interview_id}/voice")
async def voice_socket(interview_id: int, websocket: WebSocket, db: Database):
    global _voice_cleanup
    token = websocket.cookies.get(COOKIE)
    session = db.scalar(select(CandidateSession).where(
        CandidateSession.token_hash == token_digest(token))) if token else None
    if (websocket.headers.get("origin") != settings.frontend_origin or not session
            or not session.candidate.active or expired(session.candidate)
            or session.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)):
        await websocket.close(code=1008)
        return
    interview = db.scalar(select(Interview).where(Interview.id == interview_id,
                                                  Interview.candidate_id == session.candidate_id,
                                                  Interview.status == "in_progress"))
    if (not interview or interview.mode != "conversation" or not settings.openai_api_key):
        await websocket.close(code=1008)
        return
    if settings.openai_voice not in {"alloy", "ash", "ballad", "coral", "echo", "sage",
                                     "shimmer", "verse", "marin", "cedar"}:
        await websocket.close(code=1011)
        return
    candidate_id = session.candidate_id
    if _shared_limit is not None:
        try:
            allowed = _shared_limit.check(f"interview:voice:{candidate_id}", 8)
        except RateLimitUnavailable:
            await websocket.close(code=1013)
            return
        if not allowed:
            await websocket.close(code=1008)
            return
    else:
        async with _voice_lock:
            now = monotonic()
            if now - _voice_cleanup >= 60:
                prune_buckets(_voice_attempts, now)
                _voice_cleanup = now
            if candidate_id not in _voice_attempts and len(_voice_attempts) >= 30000:
                await websocket.close(code=1008)
                return
            attempts = _voice_attempts[candidate_id]
            while attempts and attempts[0] <= now - 3600:
                attempts.popleft()
            if len(attempts) >= 8:
                await websocket.close(code=1008)
                return
            attempts.append(now)
    db.rollback()
    await websocket.accept()
    try:
        async with realtime_connect(
            f"wss://api.openai.com/v1/realtime?model={settings.openai_voice_model}",
            additional_headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Safety-Identifier": hashlib.sha256(
                    f"candidate:{candidate_id}".encode()).hexdigest(),
            }, open_timeout=12, max_size=256 * 1024,
        ) as provider:
            await provider.send(json.dumps({"type": "session.update",
                                            "session": voice_session_config()["session"]}))
            await websocket.send_json({"type": "ready"})

            async def receive_client():
                nonlocal active_turn
                turns = 0
                while True:
                    raw = await websocket.receive_text()
                    if len(raw) > 256:
                        raise ValueError("Evento demasiado largo")
                    event = json.loads(raw)
                    if event.get("type") == "stop":
                        if active_turn:
                            await provider.send(json.dumps({"type": "response.cancel"}))
                            active_turn = False
                        continue
                    if event.get("type") != "speak" or turns >= 45:
                        raise ValueError("Evento no permitido")
                    await asyncio.wait_for(turn_done.wait(), timeout=8)
                    current_session = db.scalar(select(CandidateSession).where(
                        CandidateSession.token_hash == token_digest(token)))
                    current = db.scalar(select(Interview).where(
                        Interview.id == interview_id, Interview.candidate_id == candidate_id,
                        Interview.status == "in_progress"))
                    if (not current_session or not current_session.candidate.active
                            or current_session.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
                            or not current or expired(current_session.candidate)):
                        raise ValueError("Sesión vencida")
                    text = approved_voice_text(current, event.get("keys"))
                    db.rollback()
                    turns += 1
                    active_turn = True
                    turn_done.clear()
                    await provider.send(json.dumps({
                        "type": "response.create", "response": {
                            "conversation": "none", "output_modalities": ["audio"],
                            "max_output_tokens": 2000,
                            "instructions": "Leé literalmente en español rioplatense de Argentina, sin agregar comentarios ni cambiar la corrección.",
                            "input": [{"type": "message", "role": "user", "content": [
                                {"type": "input_text", "text": text}]}],
                        },
                    }))

            async def receive_provider():
                nonlocal active_turn
                async for raw in provider:
                    event = json.loads(raw)
                    kind = event.get("type")
                    if kind == "response.output_audio.delta" and isinstance(event.get("delta"), str):
                        await websocket.send_json({"type": "audio", "delta": event["delta"]})
                    elif kind == "response.output_audio_transcript.delta":
                        await websocket.send_json({"type": "transcript", "delta": event.get("delta", "")})
                    elif kind == "response.done":
                        active_turn = False
                        turn_done.set()
                        if event.get("response", {}).get("status") == "cancelled":
                            continue
                        await websocket.send_json({"type": "done",
                                                   "failed": event.get("response", {}).get("status") == "failed"})
                    elif kind == "error":
                        await websocket.send_json({"type": "error"})
                        break

            active_turn = False
            turn_done = asyncio.Event()
            turn_done.set()
            async with asyncio.timeout(1800):
                tasks = [asyncio.create_task(receive_client()), asyncio.create_task(receive_provider())]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        await task
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, ConnectionClosed, TimeoutError, ValueError):
        pass
    except Exception as exc:  # noqa: BLE001 — no filtrar información del proveedor.
        logger.warning("Falló la voz Realtime: tipo=%s", type(exc).__name__)
        try:
            await refund_voice_attempt(candidate_id)
        except RateLimitUnavailable:
            pass
        try:
            await websocket.send_json({"type": "error"})
        except RuntimeError:
            pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


@router.put("/{interview_id}/questions/{question_id}", response_model=InterviewSession)
def save_choice(interview_id: int, question_id: int, data: ChoiceInput,
                candidate: ActiveCandidate, db: Database):
    interview = ongoing(interview_id, candidate.id, db, lock=True)
    if interview.mode != "multiple_choice":
        raise HTTPException(409, "Esta entrevista no es de opción múltiple.")
    question = next((item for item in interview.responses if item.id == question_id), None)
    if question is None:
        raise HTTPException(404, "Pregunta no encontrada.")
    question.answer = str(data.selected_index) if data.selected_index is not None else None
    db.commit()
    return as_session(interview)


@router.post("/{interview_id}/questions/{question_id}/answer", response_model=InterviewSession)
async def answer_conversation(interview_id: int, question_id: int, data: AnswerInput,
                               candidate: ActiveCandidate, db: Database):
    candidate_id = candidate.id
    answer = data.answer.strip()
    if not answer:
        raise HTTPException(422, "Escribí o dictá una respuesta antes de enviarla.")
    interview = ongoing(interview_id, candidate_id, db)
    if interview.mode != "conversation":
        raise HTTPException(409, "Esta entrevista no es conversacional.")
    questions = sorted(interview.responses, key=lambda item: item.position)
    current = next((item for item in questions if item.verdict is None), None)
    if current is None or current.id != question_id:
        raise HTTPException(409, "Esta pregunta ya fue respondida o no es la pregunta actual.")
    if _capacity.locked():
        raise HTTPException(429, "El servicio está ocupado. Intentá en unos momentos.")
    previous = [item for item in questions if item.position < current.position and item.answer]
    context = "\n".join(
        f"Pregunta: {item.question[:180]} | Respuesta: {item.answer[:200]}"
        for item in previous[-2:]
    )
    evaluation_input = (current.question, current.reference_answer or "",
                        interview.vacancy.title, interview.vacancy.description, current.topic or "")
    db.rollback()
    await _capacity.acquire()
    try:
        try:
            evaluated = await evaluate_answer(
                evaluation_input[0], evaluation_input[1], answer,
                vacancy_title=evaluation_input[2], vacancy_description=evaluation_input[3],
                topic=evaluation_input[4], previous=context,
            )
        except Exception as exc:  # noqa: BLE001 — no exponer respuestas o contenido del proveedor.
            raise provider_error(exc) from None
    finally:
        _capacity.release()
    # Volver a comprobar bajo bloqueo: dos envíos simultáneos no pueden cambiar una respuesta ya guardada.
    interview = ongoing(interview_id, candidate_id, db, lock=True)
    current = next((item for item in interview.responses if item.id == question_id), None)
    if current is None or current.verdict is not None or any(
        item.position < current.position and item.verdict is None for item in interview.responses
    ):
        raise HTTPException(409, "Esta pregunta ya fue respondida o no es la pregunta actual.")
    current.answer = answer
    current.verdict = evaluated.verdict
    current.explanation = evaluated.explanation
    db.commit()
    return as_session(interview)


@router.post("/{interview_id}/finish", response_model=InterviewResult)
def finish(interview_id: int, candidate: ActiveCandidate, db: Database):
    interview = ongoing(interview_id, candidate.id, db, lock=True)
    questions = sorted(interview.responses, key=lambda item: item.position)
    if not questions:
        raise HTTPException(409, "Esta entrevista no tiene preguntas.")
    for item in questions:
        if interview.mode == "multiple_choice" and item.answer is not None:
            item.verdict = "correcta" if int(item.answer) == item.correct_index else "incorrecta"
            item.explanation = item.reference_answer
        elif item.verdict is None:
            item.verdict = "incorrecta"
            if interview.mode == "conversation":
                topic = item.topic or ""
                item.explanation = (
                    f"Sin respuesta. Repasá {topic} y cómo se aplica a esta vacante."
                    if topic and not contains_literal_code(topic)
                    else "Sin respuesta. Repasá los conceptos de esta pregunta y su aplicación en la vacante."
                )
            else:
                item.explanation = "Sin respuesta. Respuesta esperada: " + (item.reference_answer or "")
    correct = sum(item.verdict == "correcta" for item in questions)
    partial = sum(item.verdict == "parcial" for item in questions)
    missed = list(dict.fromkeys(item.topic for item in questions
                                if item.verdict != "correcta" and item.topic
                                and (interview.mode != "conversation" or not contains_literal_code(item.topic))))
    if not missed and correct != len(questions):
        missed = ["Fundamentos de la vacante"]
    interview.score = round(100 * (correct + partial / 2) / len(questions))
    interview.skills_to_improve = missed[:6]
    interview.resources = learning_resources(missed)
    interview.feedback = (f"Respondiste {correct} de {len(questions)} preguntas completamente "
                          f"y {partial} parcialmente (medio punto cada una). "
                          + ("Reforzá " + ", ".join(missed[:3]) + ". Practicá con los recursos gratuitos de abajo."
                             if missed else "¡Buen trabajo! Seguí practicando para afianzar tus conocimientos."))
    interview.status = "completed"
    db.commit()
    return result(interview_id, candidate, db)


@router.post("/{interview_id}/cancel", status_code=204)
def cancel(interview_id: int, candidate: ActiveCandidate, db: Database):
    interview = ongoing(interview_id, candidate.id, db, lock=True)
    interview.status = "cancelled"
    db.commit()


@router.get("", response_model=list[InterviewSummary])
def history(candidate: ActiveCandidate, db: Database,
            limit: int = Query(default=20, ge=1, le=100),
            before: int | None = Query(default=None, gt=0)):
    query = (select(Interview, Vacancy.title)
             .join(Vacancy, Interview.vacancy_id == Vacancy.id)
             .where(Interview.candidate_id == candidate.id,
                    Interview.active.is_(True), Interview.status == "completed",
                    Interview.score.is_not(None)))
    if before is not None:
        anchor = db.scalar(select(Interview).where(Interview.id == before,
                                                    Interview.candidate_id == candidate.id))
        if anchor is None:
            raise HTTPException(404, "Entrevista no encontrada.")
        query = query.where(or_(Interview.created_at < anchor.created_at,
                                and_(Interview.created_at == anchor.created_at,
                                     Interview.id < anchor.id)))
    rows = db.execute(
        query.order_by(Interview.created_at.desc(), Interview.id.desc()).limit(limit)
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
    questions = sorted(interview.responses, key=lambda item: item.position)
    return InterviewResult(id=interview.id, vacancy_title=title,
                            created_at=interview.created_at, score=interview.score,
                            feedback=interview.feedback,
                            skills_to_improve=interview.skills_to_improve or [],
                            mode=interview.mode, correct_count=sum(q.verdict == "correcta" for q in questions),
                            partial_count=sum(q.verdict == "parcial" for q in questions),
                            incorrect_count=sum(q.verdict == "incorrecta" for q in questions),
                            unanswered_count=sum(q.answer is None for q in questions),
                            resources=interview.resources or [], questions=questions_for(interview, finished=True))


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
