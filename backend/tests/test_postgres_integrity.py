"""Integración opcional: ejecutar solo con TEST_DATABASE_URL de una DB de pruebas migrada."""

import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Candidate, Interview, Vacancy


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requiere PostgreSQL aislado")
def test_postgres_interview_constraints():
    url = os.environ["TEST_DATABASE_URL"]
    # No ejecutar inserciones si alguien apunta accidentalmente a su DB principal.
    if not url.rsplit("/", 1)[-1].startswith("tfg_audit_"):
        pytest.fail("TEST_DATABASE_URL debe apuntar a una DB aislada tfg_audit_*")
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            candidate = Candidate(email="audit-integrity@example.test", first_name="Prueba",
                                  last_name="Integridad")
            db.add(candidate)
            db.flush()
            vacancy = Vacancy(candidate_id=candidate.id, title="Python", description="Oferta de prueba")
            db.add(vacancy)
            db.flush()
            db.add(Interview(candidate_id=candidate.id, vacancy_id=vacancy.id,
                             mode="conversation", status="in_progress"))
            db.flush()
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(Interview(candidate_id=candidate.id, vacancy_id=vacancy.id,
                                 mode="conversation", status="in_progress"))
                db.flush()
            assert db.scalar(select(Interview.id).where(
                Interview.candidate_id == candidate.id)) is not None
            db.rollback()
    finally:
        engine.dispose()
