"""Perfil y documentos privados de cada candidato."""

import io
import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select, update

from app.core.config import settings
from app.db.models import Candidate, Resume
from app.modules.auth.router import ActiveCandidate, CandidateOutput, Database, public_candidate

router = APIRouter(prefix="/profile", tags=["perfil"])
MAX_FILE_BYTES = 5 * 1024 * 1024


def destination(kind: str, suffix: str) -> tuple[str, Path]:
    folder = datetime.now().strftime("%Y_%m_%d")
    name = f"{'imagen' if kind == 'images' else 'cv'}_{secrets.token_hex(16)}.{suffix}"
    key = f"{kind}/{folder}/{name}"
    path = settings.media_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    return key, path


def stored_file(key: str, kind: str) -> Path:
    root = (settings.media_dir / kind).resolve()
    path = (settings.media_dir / key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Archivo no disponible.")
    return path


async def read_limited(file: UploadFile) -> bytes:
    content = await file.read(MAX_FILE_BYTES + 1)
    if not content or len(content) > MAX_FILE_BYTES:
        raise HTTPException(422, "El archivo debe tener hasta 5 MB.")
    return content


class NicknameInput(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)

    @field_validator("nickname")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ingresá un apodo.")
        return value


class ResumeOutput(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    is_primary: bool


@router.patch("", response_model=CandidateOutput)
def change_nickname(data: NicknameInput, candidate: ActiveCandidate, db: Database):
    candidate.nickname = data.nickname
    db.commit()
    return public_candidate(candidate)


@router.post("/avatar", response_model=CandidateOutput)
async def upload_avatar(candidate: ActiveCandidate, db: Database, file: Annotated[UploadFile, File()]):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(422, "Elegí una imagen JPG, PNG o WebP.")
    content = await read_limited(file)
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width != image.height or image.width > 2048 or image.width < 64:
                raise HTTPException(422, "La foto recortada debe ser cuadrada (64 a 2048 píxeles).")
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, format="WEBP", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "La imagen no es válida.") from None
    key, path = destination("images", "webp")
    old_key = candidate.avatar_key
    try:
        path.write_bytes(output.getvalue())
        candidate.avatar_key = key
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    if old_key:
        try:
            stored_file(old_key, "images").unlink(missing_ok=True)
        except HTTPException:
            pass
    return public_candidate(candidate)


@router.get("/avatar")
def get_avatar(candidate: ActiveCandidate):
    if not candidate.avatar_key:
        raise HTTPException(404, "No hay foto de perfil.")
    return FileResponse(stored_file(candidate.avatar_key, "images"), media_type="image/webp",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/resumes", response_model=list[ResumeOutput])
def list_resumes(candidate: ActiveCandidate, db: Database):
    return db.scalars(select(Resume).where(Resume.candidate_id == candidate.id)
                      .order_by(Resume.uploaded_at.desc(), Resume.id.desc())).all()


@router.post("/resumes", response_model=ResumeOutput, status_code=201)
async def upload_resume(candidate: ActiveCandidate, db: Database, file: Annotated[UploadFile, File()]):
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".pdf") or len(filename) > 255 or file.content_type != "application/pdf":
        raise HTTPException(422, "Seleccioná un PDF de hasta 5 MB.")
    content = await read_limited(file)
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise HTTPException(422, "El archivo no es un PDF válido.")
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if not reader.pages:
            raise HTTPException(422, "El PDF debe contener al menos una página.")
    except (PdfReadError, ValueError, OSError, KeyError):
        raise HTTPException(422, "El archivo no es un PDF válido.") from None
    db.scalar(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    has_primary = db.scalar(select(Resume.id).where(Resume.candidate_id == candidate.id, Resume.is_primary))
    key, path = destination("files", "pdf")
    resume = Resume(candidate_id=candidate.id, filename=filename, storage_key=key,
                    is_primary=has_primary is None)
    try:
        path.write_bytes(content)
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    return resume


@router.patch("/resumes/{resume_id}/primary", response_model=ResumeOutput)
def make_primary(resume_id: int, candidate: ActiveCandidate, db: Database):
    db.scalar(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.candidate_id == candidate.id))
    if not resume:
        raise HTTPException(404, "Currículum no encontrado.")
    db.execute(update(Resume).where(Resume.candidate_id == candidate.id, Resume.is_primary)
               .values(is_primary=False))
    db.flush()
    resume.is_primary = True
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes/{resume_id}/download")
def download_resume(resume_id: int, candidate: ActiveCandidate, db: Database):
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.candidate_id == candidate.id))
    if not resume:
        raise HTTPException(404, "Currículum no encontrado.")
    return FileResponse(stored_file(resume.storage_key, "files"), media_type="application/pdf",
                        filename=resume.filename,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
