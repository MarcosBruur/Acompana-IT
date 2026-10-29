"""Sesiones, caducidad de contraseñas e identidades Google.

Revision ID: 0002_auth
Revises: 0001_initial
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0002_auth"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE candidates SET password_changed_at = created_at WHERE password_hash IS NOT NULL"
    )
    op.create_table(
        "candidate_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidate_sessions_candidate_id", "candidate_sessions", ["candidate_id"])
    op.create_table(
        "google_identities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("google_sub", sa.String(255), unique=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("google_identities")
    op.drop_index("ix_candidate_sessions_candidate_id", table_name="candidate_sessions")
    op.drop_table("candidate_sessions")
    op.drop_column("candidates", "password_changed_at")
