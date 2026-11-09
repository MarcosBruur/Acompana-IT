"""Índices de consulta y restricciones de entrevistas.

Revision ID: 0011_audit_integrity
Revises: 0010_interview_simulation
"""

import sqlalchemy as sa

from alembic import op

revision = "0011_audit_integrity"
down_revision = "0010_interview_simulation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La creación del índice único detiene la migración si ya existen entrevistas
    # simultáneas: resolverlas explícitamente antes de aplicar esta revisión.
    op.create_index("uq_interviews_ongoing_candidate", "interviews", ["candidate_id"],
                    unique=True, postgresql_where=sa.text("status = 'in_progress'"))
    op.create_index("ix_interviews_candidate_active_recent", "interviews",
                    ["candidate_id", "active", "created_at", "id"])
    op.create_index("ix_vacancies_candidate_active_recent", "vacancies",
                    ["candidate_id", "active", "created_at", "id"])
    op.create_index("ix_resumes_candidate_active_recent", "resumes",
                    ["candidate_id", "active", "uploaded_at", "id"])
    op.create_index("uq_interview_responses_position", "interview_responses",
                    ["interview_id", "position"], unique=True)
    op.create_check_constraint("ck_interviews_mode", "interviews",
                               "mode IN ('conversation', 'multiple_choice')")
    op.create_check_constraint("ck_interviews_status", "interviews",
                               "status IN ('in_progress', 'completed', 'cancelled')")
    op.create_check_constraint("ck_interviews_score", "interviews",
                               "score IS NULL OR score BETWEEN 0 AND 100")
    op.create_check_constraint("ck_interview_responses_position", "interview_responses", "position > 0")
    op.create_check_constraint("ck_interview_responses_correct_index", "interview_responses",
                               "correct_index IS NULL OR correct_index BETWEEN 0 AND 3")
    op.create_check_constraint("ck_interview_responses_verdict", "interview_responses",
                               "verdict IS NULL OR verdict IN ('correcta', 'parcial', 'incorrecta')")


def downgrade() -> None:
    for name in ("ck_interview_responses_verdict", "ck_interview_responses_correct_index",
                 "ck_interview_responses_position"):
        op.drop_constraint(name, "interview_responses", type_="check")
    for name in ("ck_interviews_score", "ck_interviews_status", "ck_interviews_mode"):
        op.drop_constraint(name, "interviews", type_="check")
    op.drop_index("uq_interview_responses_position", table_name="interview_responses")
    op.drop_index("ix_resumes_candidate_active_recent", table_name="resumes")
    op.drop_index("ix_vacancies_candidate_active_recent", table_name="vacancies")
    op.drop_index("ix_interviews_candidate_active_recent", table_name="interviews")
    op.drop_index("uq_interviews_ongoing_candidate", table_name="interviews")
