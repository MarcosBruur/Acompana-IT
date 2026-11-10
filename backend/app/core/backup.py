"""Crear respaldo consistente de PostgreSQL y medios privados en un destino configurado."""

import os
import secrets
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import settings


def main() -> None:
    if settings.backup_dir is None:
        raise SystemExit("Configurá BACKUP_DIR antes de crear respaldos.")
    target = settings.backup_dir.resolve()
    workspace = Path(__file__).resolve().parents[3]
    if target.is_relative_to(settings.media_dir.resolve()) or target.is_relative_to(workspace):
        raise SystemExit("BACKUP_DIR debe estar fuera de MEDIA_DIR y del repositorio.")
    target.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(4)
    database_file = target / f"postgres_{suffix}.dump"
    media_file = target / f"medios_{suffix}.tar.gz"
    database_temp = database_file.with_suffix(".dump.tmp")
    media_temp = media_file.with_suffix(".tar.gz.tmp")
    url = make_url(settings.database_url)
    environment = {**os.environ, "PGHOST": url.host or "localhost",
                   "PGPORT": str(url.port or 5432), "PGUSER": url.username or "",
                   "PGPASSWORD": url.password or "", "PGDATABASE": url.database or ""}
    if settings.backup_db_container:
        if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in settings.backup_db_container):
            raise SystemExit("BACKUP_DB_CONTAINER no es válido.")
        command = ["docker", "exec", settings.backup_db_container, "pg_dump", "-U",
                   url.username or "", "-Fc", url.database or ""]
    else:
        command = [settings.pg_dump_path, "--format=custom", "--file", str(database_temp)]
    try:
        if settings.backup_db_container:
            with database_temp.open("wb") as output:
                result = subprocess.run(command, env=environment, stdout=output,
                                        stderr=subprocess.PIPE, check=False, timeout=1800)
        else:
            result = subprocess.run(command, env=environment, check=False,
                                    capture_output=True, timeout=1800)
        if result.returncode or not database_temp.is_file() or not database_temp.stat().st_size:
            raise RuntimeError("No se pudo generar el respaldo PostgreSQL.")
        with tarfile.open(media_temp, "w:gz") as archive:
            for kind in ("images", "files"):
                folder = settings.media_dir / kind
                if folder.is_dir():
                    archive.add(folder, arcname=kind, recursive=True, filter=lambda info: (
                        None if info.issym() or info.islnk() else info))
        database_temp.replace(database_file)
        media_temp.replace(media_file)
    except (OSError, subprocess.TimeoutExpired, RuntimeError, tarfile.TarError):
        database_temp.unlink(missing_ok=True)
        media_temp.unlink(missing_ok=True)
        database_file.unlink(missing_ok=True)
        media_file.unlink(missing_ok=True)
        raise SystemExit("No se pudo completar el respaldo; verificá BACKUP_DIR y PG_DUMP_PATH.") from None
    print("Respaldo PostgreSQL y medios completado.")


if __name__ == "__main__":
    main()
