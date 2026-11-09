"""Datos de simulación, preguntas y resultados.

Revision ID: 0010_interview_simulation
Revises: 0009_resume_active
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0010_interview_simulation"
down_revision = "0009_resume_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("resume_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_interviews_resume", "interviews", "resumes", ["resume_id"], ["id"],
                          ondelete="SET NULL")
    op.add_column("interviews", sa.Column("mode", sa.String(20), nullable=False,
                                          server_default="conversation"))
    op.add_column("interviews", sa.Column("resources", JSONB(), nullable=True))
    op.add_column("interview_responses", sa.Column("topic", sa.String(150), nullable=True))
    op.add_column("interview_responses", sa.Column("options", JSONB(), nullable=True))
    op.add_column("interview_responses", sa.Column("correct_index", sa.Integer(), nullable=True))
    op.add_column("interview_responses", sa.Column("reference_answer", sa.Text(), nullable=True))
    op.add_column("interview_responses", sa.Column("verdict", sa.String(20), nullable=True))
    op.add_column("interview_responses", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    for column in ("explanation", "verdict", "reference_answer", "correct_index", "options", "topic"):
        op.drop_column("interview_responses", column)
    op.drop_column("interviews", "resources")
    op.drop_column("interviews", "mode")
    op.drop_constraint("fk_interviews_resume", "interviews", type_="foreignkey")
    op.drop_column("interviews", "resume_id")
