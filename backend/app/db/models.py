"""Esquema inicial; se ampliará al implementar cada historia de usuario."""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate")
    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="candidate")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    candidate: Mapped[Candidate] = relationship(back_populates="resumes")


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    candidate: Mapped[Candidate | None] = relationship(back_populates="vacancies")
    analysis: Mapped["VacancyAnalysis | None"] = relationship(back_populates="vacancy")


class VacancyAnalysis(Base):
    __tablename__ = "vacancy_analyses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), unique=True)
    seniority: Mapped[str | None] = mapped_column(String(50))
    required_skills: Mapped[list] = mapped_column(JSONB, default=list)
    technologies: Mapped[list] = mapped_column(JSONB, default=list)
    inconsistencies: Mapped[list] = mapped_column(JSONB, default=list)
    risk_signals: Mapped[list] = mapped_column(JSONB, default=list)
    risk_percentage: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    vacancy: Mapped[Vacancy] = relationship(back_populates="analysis")


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    # Sin dimensión fija hasta escoger un modelo de embeddings.
    embedding: Mapped[list[float] | None] = mapped_column(Vector())


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    resume_id: Mapped[UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    missing_skills: Mapped[list] = mapped_column(JSONB, default=list)
    gap_percentage: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    score: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    skills_to_improve: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responses: Mapped[list["InterviewResponse"]] = relationship(back_populates="interview")


class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interview_id: Mapped[UUID] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    interview: Mapped[Interview] = relationship(back_populates="responses")


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    competency_id: Mapped[UUID] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    is_free: Mapped[bool] = mapped_column(default=True)
