import os
from time import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.media_maintenance import reconcile
from app.db.base import Base
from app.db.models import Candidate, Resume


def test_media_reconciliation_retains_references_and_recent_uploads(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'media.db'}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__, Resume.__table__])
    root = tmp_path / "media"
    folder = root / "files" / "2026_11_09"
    folder.mkdir(parents=True)
    kept_key = "files/2026_11_09/cv_" + "a" * 32 + ".pdf"
    orphan = folder / ("cv_" + "b" * 32 + ".pdf")
    recent = folder / ("cv_" + "c" * 32 + ".pdf")
    for path in (root / kept_key, orphan, recent):
        path.write_bytes(b"%PDF-test")
    os.utime(orphan, (time() - 90000, time() - 90000))
    try:
        with Session(engine) as db:
            candidate = Candidate(email="test@example.com", first_name="Ana", last_name="Pérez")
            db.add(candidate)
            db.flush()
            db.add(Resume(candidate_id=candidate.id, filename="privado.pdf", storage_key=kept_key))
            db.commit()
            assert reconcile(db, root) == {"referencias_sin_archivo": 0,
                                            "huerfanos_antiguos": 1, "huerfanos_eliminados": 0}
            assert reconcile(db, root, delete=True)["huerfanos_eliminados"] == 1
            assert (root / kept_key).exists() and recent.exists() and not orphan.exists()
            (root / kept_key).unlink()
            assert reconcile(db, root, delete=True)["referencias_sin_archivo"] == 1
    finally:
        engine.dispose()
