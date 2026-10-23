"""Esquema inicial y extensión pgvector.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "candidates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidates_email", "candidates", ["email"], unique=True)
    op.create_table(
        "competencies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), unique=True, nullable=False),
        sa.Column("embedding", Vector()),
    )
    op.create_table(
        "resumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "vacancies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "vacancy_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vacancy_id", UUID(as_uuid=True), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("seniority", sa.String(50)),
        sa.Column("required_skills", JSONB(), nullable=False),
        sa.Column("technologies", JSONB(), nullable=False),
        sa.Column("inconsistencies", JSONB(), nullable=False),
        sa.Column("risk_signals", JSONB(), nullable=False),
        sa.Column("risk_percentage", sa.Integer()),
        sa.Column("summary", sa.Text()),
    )
    op.create_table(
        "comparisons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vacancy_id", UUID(as_uuid=True), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("missing_skills", JSONB(), nullable=False),
        sa.Column("gap_percentage", sa.Integer()),
        sa.Column("feedback", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "interviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vacancy_id", UUID(as_uuid=True), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("feedback", sa.Text()),
        sa.Column("skills_to_improve", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "interview_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("interview_id", UUID(as_uuid=True), sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_table(
        "learning_resources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("competency_id", UUID(as_uuid=True), sa.ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "learning_resources", "interview_responses", "interviews", "comparisons",
        "vacancy_analyses", "vacancies", "resumes", "competencies", "candidates",
    ):
        op.drop_table(table)
    # La extensión puede ser compartida con otras tablas: no eliminarla automáticamente.
