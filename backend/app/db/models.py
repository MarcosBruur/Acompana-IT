"""Esquema inicial; se ampliará al implementar cada historia de usuario."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str | None] = mapped_column(String(100))
    avatar_key: Mapped[str | None] = mapped_column(String(500))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate")
    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="candidate")


class CandidateSession(Base):
    __tablename__ = "candidate_sessions"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candidate: Mapped[Candidate] = relationship()


class GoogleIdentity(Base):
    __tablename__ = "google_identities"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), unique=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    candidate: Mapped[Candidate] = relationship()


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("uq_resumes_primary_candidate", "candidate_id", unique=True,
                            postgresql_where=text("is_primary"), sqlite_where=text("is_primary")),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    candidate: Mapped[Candidate] = relationship(back_populates="resumes")


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    candidate: Mapped[Candidate | None] = relationship(back_populates="vacancies")
    analysis: Mapped["VacancyAnalysis | None"] = relationship(back_populates="vacancy")


class VacancyAnalysis(Base):
    __tablename__ = "vacancy_analyses"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), unique=True)
    seniority: Mapped[str | None] = mapped_column(String(50))
    experience_required: Mapped[str | None] = mapped_column(String(100))
    required_skills: Mapped[list] = mapped_column(JSONB, default=list)
    technologies: Mapped[list] = mapped_column(JSONB, default=list)
    responsibilities: Mapped[list] = mapped_column(JSONB, default=list)
    inconsistencies: Mapped[list] = mapped_column(JSONB, default=list)
    risk_signals: Mapped[list] = mapped_column(JSONB, default=list)
    risk_percentage: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    vacancy: Mapped[Vacancy] = relationship(back_populates="analysis")


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    # Sin dimensión fija hasta escoger un modelo de embeddings.
    embedding: Mapped[list[float] | None] = mapped_column(Vector())


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    missing_skills: Mapped[list] = mapped_column(JSONB, default=list)
    gap_percentage: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    score: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    skills_to_improve: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vacancy: Mapped[Vacancy] = relationship()
    responses: Mapped[list["InterviewResponse"]] = relationship(back_populates="interview")


class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    interview: Mapped[Interview] = relationship(back_populates="responses")


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    is_free: Mapped[bool] = mapped_column(default=True)
