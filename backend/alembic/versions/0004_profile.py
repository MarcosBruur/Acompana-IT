"""Apodo, foto y CV principal.

Revision ID: 0004_profile
Revises: 0003_integer_ids
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_profile"
down_revision = "0003_integer_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("nickname", sa.String(100), nullable=True))
    op.add_column("candidates", sa.Column("avatar_key", sa.String(500), nullable=True))
    op.add_column("resumes", sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("""UPDATE resumes SET is_primary = true WHERE id IN (
        SELECT DISTINCT ON (candidate_id) id FROM resumes ORDER BY candidate_id, uploaded_at DESC, id DESC
    )""")
    op.create_index("uq_resumes_primary_candidate", "resumes", ["candidate_id"], unique=True,
                    postgresql_where=sa.text("is_primary"))


def downgrade() -> None:
    op.drop_index("uq_resumes_primary_candidate", table_name="resumes")
    op.drop_column("resumes", "is_primary")
    op.drop_column("candidates", "avatar_key")
    op.drop_column("candidates", "nickname")
