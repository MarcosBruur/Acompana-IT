import subprocess
import tarfile
from pathlib import Path

from app.core import backup
from app.core.config import settings


def test_backup_writes_db_and_private_media_outside_workspace(tmp_path, monkeypatch):
    media = tmp_path / "media"
    (media / "files").mkdir(parents=True)
    (media / "files" / "cv.pdf").write_bytes(b"privado")
    monkeypatch.setattr(settings, "media_dir", media)
    monkeypatch.setattr(settings, "backup_dir", tmp_path / "backups")
    monkeypatch.setattr(settings, "backup_db_container", None)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://test:secreto@127.0.0.1:5433/tfg")

    def pg_dump(command, **_kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"respaldo")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(backup.subprocess, "run", pg_dump)
    backup.main()
    db_file = next(settings.backup_dir.glob("*.dump"))
    media_file = next(settings.backup_dir.glob("*.tar.gz"))
    assert db_file.read_bytes() == b"respaldo"
    with tarfile.open(media_file) as archive:
        assert archive.extractfile("files/cv.pdf").read() == b"privado"
