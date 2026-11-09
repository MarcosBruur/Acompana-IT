"""Ocultación reversible de entrevistas en el historial.

Revision ID: 0006_interview_active
Revises: 0005_vacancy_analysis
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_interview_active"
down_revision = "0005_vacancy_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("active", sa.Boolean(), nullable=False,
                                         server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("interviews", "active")
