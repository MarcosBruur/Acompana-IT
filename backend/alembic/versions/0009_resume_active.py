"""Ocultación de currículums sin borrar documentos ni comparaciones.

Revision ID: 0009_resume_active
Revises: 0008_vacancy_active
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_resume_active"
down_revision = "0008_vacancy_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("active", sa.Boolean(), nullable=False,
                                      server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("resumes", "active")
