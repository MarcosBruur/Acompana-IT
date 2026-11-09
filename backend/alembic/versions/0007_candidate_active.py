"""Estado activo de los candidatos.

Revision ID: 0007_candidate_active
Revises: 0006_interview_active
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_candidate_active"
down_revision = "0006_interview_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("active", sa.Boolean(), nullable=False,
                                          server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("candidates", "active")
