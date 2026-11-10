"""Exención administrativa de límites por candidato.

Revision ID: 0013_candidate_admin
Revises: 0012_comparison_ownership
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_candidate_admin"
down_revision = "0012_comparison_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("admin", sa.Boolean(), nullable=False,
                                          server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("candidates", "admin")
