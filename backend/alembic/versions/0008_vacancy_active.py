"""Estado activo de las vacantes.

Revision ID: 0008_vacancy_active
Revises: 0007_candidate_active
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_vacancy_active"
down_revision = "0007_candidate_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("active", sa.Boolean(), nullable=False,
                                         server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("vacancies", "active")
