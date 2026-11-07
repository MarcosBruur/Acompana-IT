"""Experiencia y responsabilidades de los análisis de vacantes.

Revision ID: 0005_vacancy_analysis
Revises: 0004_profile
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005_vacancy_analysis"
down_revision = "0004_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancy_analyses", sa.Column("experience_required", sa.String(100)))
    op.add_column("vacancy_analyses", sa.Column("responsibilities", JSONB(),
                  nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.alter_column("vacancy_analyses", "responsibilities", server_default=None)


def downgrade() -> None:
    op.drop_column("vacancy_analyses", "responsibilities")
    op.drop_column("vacancy_analyses", "experience_required")
