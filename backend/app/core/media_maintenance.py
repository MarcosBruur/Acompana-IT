"""Conciliar DB y medios privados; nunca mostrar contenido ni rutas individuales."""

import argparse
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Candidate, Resume
from app.db.session import engine

MEDIA_NAME = re.compile(r"^(?:images/\d{4}_\d{2}_\d{2}/imagen_[0-9a-f]{32}\.webp|"
                        r"files/\d{4}_\d{2}_\d{2}/cv_[0-9a-f]{32}\.pdf)$")


def reconcile(db: Session, root: Path, *, delete: bool = False,
              min_age_hours: int = 24) -> dict[str, int]:
    root = root.resolve()
    referenced = set(db.scalars(select(Resume.storage_key)).all())
    referenced.update(db.scalars(select(Candidate.avatar_key).where(
        Candidate.avatar_key.is_not(None))).all())
    missing = sum(not MEDIA_NAME.fullmatch(key) or not (root / key).is_file()
                  for key in referenced if key)
    threshold = datetime.now(UTC) - timedelta(hours=min_age_hours)
    orphaned = 0
    removed = 0
    for kind in ("files", "images"):
        for path in (root / kind).glob("*/*"):
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            key = path.relative_to(root).as_posix()
            if not MEDIA_NAME.fullmatch(key) or key in referenced:
                continue
            if datetime.fromtimestamp(path.stat().st_mtime, UTC) > threshold:
                continue
            orphaned += 1
            if delete and not missing:
                path.unlink()
                removed += 1
    return {"referencias_sin_archivo": missing, "huerfanos_antiguos": orphaned,
            "huerfanos_eliminados": removed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Conciliar medios y metadatos privados.")
    parser.add_argument("--delete-orphans", action="store_true",
                        help="Eliminar solo archivos huérfanos de más de 24 horas.")
    args = parser.parse_args()
    with Session(engine) as db:
        summary = reconcile(db, settings.media_dir, delete=args.delete_orphans)
    for name, count in summary.items():
        print(f"{name}: {count}")
    if args.delete_orphans and summary["referencias_sin_archivo"]:
        raise SystemExit("Hay archivos referenciados ausentes: no se eliminó ningún huérfano.")


if __name__ == "__main__":
    main()
