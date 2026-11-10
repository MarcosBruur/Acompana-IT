"""Impedir comparaciones entre CV, vacantes y candidatos de distintos propietarios.

Revision ID: 0012_comparison_ownership
Revises: 0011_audit_integrity
"""

from alembic import op

revision = "0012_comparison_ownership"
down_revision = "0011_audit_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Una comparación preexistente con relaciones cruzadas provocará un error de FK:
    # corregir los datos respaldados en lugar de borrarlos automáticamente.
    op.create_unique_constraint("uq_resumes_id_candidate", "resumes", ["id", "candidate_id"])
    op.create_unique_constraint("uq_vacancies_id_candidate", "vacancies", ["id", "candidate_id"])
    op.create_foreign_key("fk_comparisons_owned_resume", "comparisons", "resumes",
                          ["resume_id", "candidate_id"], ["id", "candidate_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_comparisons_owned_vacancy", "comparisons", "vacancies",
                          ["vacancy_id", "candidate_id"], ["id", "candidate_id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_comparisons_owned_vacancy", "comparisons", type_="foreignkey")
    op.drop_constraint("fk_comparisons_owned_resume", "comparisons", type_="foreignkey")
    op.drop_constraint("uq_vacancies_id_candidate", "vacancies", type_="unique")
    op.drop_constraint("uq_resumes_id_candidate", "resumes", type_="unique")
