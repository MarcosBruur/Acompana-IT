"""Autenticación de candidatos; las sesiones son cookies opacas revocables."""

import base64
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationInfo, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Candidate, CandidateSession, GoogleIdentity
from app.db.session import SessionLocal

router = APIRouter(prefix="/auth", tags=["cuentas"])
hasher = PasswordHasher()
COOKIE = "candidate_session"
SESSION_LIFETIME = timedelta(days=7)
PASSWORD_LIFETIME = timedelta(days=200)


def db_session():
    with SessionLocal() as db:
        yield db


Database = Annotated[Session, Depends(db_session)]


def valid_password(value: str) -> str:
    if (
        len(value) < 8
        or not re.search(r"[A-Z]", value)
        or not re.search(r"[0-9]", value)
        or not re.search(r"[^A-Za-z0-9]", value)
    ):
        raise ValueError("Usá al menos 8 caracteres, una mayúscula, un número y un carácter especial.")
    return value


class RegisterInput(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(max_length=1024)
    confirm_password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return valid_password(value)

    @field_validator("confirm_password")
    @classmethod
    def check_confirmation(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Las contraseñas deben coincidir.")
        return value


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(max_length=1024)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return valid_password(value)

    @field_validator("confirm_password")
    @classmethod
    def check_confirmation(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("Las contraseñas deben coincidir.")
        return value


class CandidateOutput(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    password_expired: bool
    role: str = "candidato"


def expired(candidate: Candidate) -> bool:
    changed_at = candidate.password_changed_at
    if changed_at is not None and changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=UTC)
    return bool(
        candidate.password_hash
        and (
            changed_at is None
            or datetime.now(UTC) >= changed_at + PASSWORD_LIFETIME
        )
    )


def public_candidate(candidate: Candidate) -> CandidateOutput:
    return CandidateOutput(
        id=candidate.id, email=candidate.email, first_name=candidate.first_name,
        last_name=candidate.last_name, password_expired=expired(candidate),
    )


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name, value, max_age=max_age, httponly=True, secure=settings.cookie_secure,
        samesite="lax", path="/",
    )


def create_session(db: Session, response: Response, candidate: Candidate) -> None:
    token = secrets.token_urlsafe(48)
    db.add(CandidateSession(
        candidate_id=candidate.id, token_hash=token_digest(token),
        expires_at=datetime.now(UTC) + SESSION_LIFETIME,
    ))
    db.commit()
    set_cookie(response, COOKIE, token, int(SESSION_LIFETIME.total_seconds()))


def current_session(request: Request, db: Database) -> CandidateSession:
    token = request.cookies.get(COOKIE)
    session = db.scalar(select(CandidateSession).where(CandidateSession.token_hash == token_digest(token))) if token else None
    expires_at = session.expires_at.replace(tzinfo=UTC) if session and session.expires_at.tzinfo is None else session.expires_at if session else None
    if not session or expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Iniciá sesión para continuar.")
    return session


SessionDependency = Annotated[CandidateSession, Depends(current_session)]


def active_candidate(session: SessionDependency) -> Candidate:
    if expired(session.candidate):
        raise HTTPException(403, "Contraseña vencida. Cambiala para continuar.")
    return session.candidate


ActiveCandidate = Annotated[Candidate, Depends(active_candidate)]


@router.post("/register", response_model=CandidateOutput, status_code=201)
def register(data: RegisterInput, response: Response, db: Database):
    email = str(data.email).lower()
    if db.scalar(select(Candidate.id).where(Candidate.email == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    candidate = Candidate(
        email=email, first_name=data.first_name.strip(), last_name=data.last_name.strip(),
        password_hash=hasher.hash(data.password), password_changed_at=datetime.now(UTC),
    )
    if not candidate.first_name or not candidate.last_name:
        raise HTTPException(422, "Ingresá nombre y apellido.")
    try:
        db.add(candidate)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe una cuenta con ese correo.") from None
    create_session(db, response, candidate)
    return public_candidate(candidate)


@router.post("/login", response_model=CandidateOutput)
def login(data: LoginInput, response: Response, db: Database):
    candidate = db.scalar(select(Candidate).where(Candidate.email == str(data.email).lower()))
    try:
        verified = bool(candidate and candidate.password_hash and hasher.verify(candidate.password_hash, data.password))
    except (VerifyMismatchError, InvalidHashError):
        verified = False
    if not verified:
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    create_session(db, response, candidate)
    return public_candidate(candidate)


@router.get("/me", response_model=CandidateOutput)
def me(session: SessionDependency):
    return public_candidate(session.candidate)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database):
    token = request.cookies.get(COOKIE)
    if token:
        session = db.scalar(select(CandidateSession).where(CandidateSession.token_hash == token_digest(token)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


@router.post("/change-password", response_model=CandidateOutput)
def change_password(data: ChangePasswordInput, response: Response, db: Database, session: SessionDependency):
    candidate = session.candidate
    if not candidate.password_hash:
        raise HTTPException(400, "Esta cuenta usa Google para iniciar sesión.")
    try:
        is_current = hasher.verify(candidate.password_hash, data.current_password)
    except (VerifyMismatchError, InvalidHashError):
        is_current = False
    try:
        is_previous = hasher.verify(candidate.password_hash, data.new_password)
    except (VerifyMismatchError, InvalidHashError):
        is_previous = False
    if not is_current:
        raise HTTPException(401, "La contraseña actual es incorrecta.")
    if is_previous:
        raise HTTPException(422, "La nueva contraseña debe ser distinta de la anterior.")
    candidate.password_hash = hasher.hash(data.new_password)
    candidate.password_changed_at = datetime.now(UTC)
    db.query(CandidateSession).filter(CandidateSession.candidate_id == candidate.id).delete()
    db.flush()
    create_session(db, response, candidate)
    return public_candidate(candidate)


def google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


@router.get("/google/available")
def google_available() -> dict[str, bool]:
    return {"available": google_configured()}


@router.get("/google")
def google_start():
    if not google_configured():
        raise HTTPException(503, "El acceso con Google todavía no está configurado.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.backend_origin}/api/v1/auth/google/callback",
        "response_type": "code", "scope": "openid email profile", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    })
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")
    set_cookie(response, "google_state", state, 600)
    set_cookie(response, "google_verifier", verifier, 600)
    return response


@router.get("/google/callback")
async def google_callback(request: Request, db: Database):
    error_redirect = f"{settings.frontend_origin}/sesion?google_error=1"
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    verifier = request.cookies.get("google_verifier")
    if not google_configured() or not code or not state or not verifier or not secrets.compare_digest(state, request.cookies.get("google_state", "")):
        return RedirectResponse(error_redirect)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.backend_origin}/api/v1/auth/google/callback",
                "grant_type": "authorization_code", "code_verifier": verifier,
            })
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
        if profile.get("email_verified") is not True or not profile.get("sub"):
            return RedirectResponse(error_redirect)
        email = str(TypeAdapter(EmailStr).validate_python(profile["email"])).lower()
        identity = db.scalar(select(GoogleIdentity).where(GoogleIdentity.google_sub == str(profile["sub"])))
        if identity:
            candidate = identity.candidate
        else:
            # No vincular automáticamente cuentas locales por email: requiere prueba de posesión de ambas.
            if db.scalar(select(Candidate.id).where(Candidate.email == email)):
                return RedirectResponse(f"{settings.frontend_origin}/sesion?google_error=linked")
            candidate = Candidate(
                email=email, first_name=str(profile.get("given_name") or "Candidato")[:100],
                last_name=str(profile.get("family_name") or "Google")[:100],
            )
            db.add(candidate)
            db.flush()
            db.add(GoogleIdentity(candidate_id=candidate.id, google_sub=str(profile["sub"])))
            db.commit()
    except (httpx.HTTPError, KeyError, ValueError, IntegrityError):
        db.rollback()
        return RedirectResponse(error_redirect)
    response = RedirectResponse(settings.frontend_origin + "/")
    response.delete_cookie("google_state", path="/")
    response.delete_cookie("google_verifier", path="/")
    create_session(db, response, candidate)
    return response
