import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import Candidate, CandidateSession, Resume
from app.main import app
from app.modules.auth.router import db_session

API = "/api/v1/profile"


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__, CandidateSession.__table__, Resume.__table__])
    monkeypatch.setattr(settings, "media_dir", tmp_path / "media")

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[db_session] = session
    with TestClient(app, base_url="http://localhost:8000",
                    headers={"Origin": "http://localhost:5173"}) as http:
        yield http, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(http, email):
    return http.post("/api/v1/auth/register", json={
        "email": email, "first_name": "Ana", "last_name": "Pérez",
        "password": "ClaveSegura1!", "confirm_password": "ClaveSegura1!",
    })


def pdf():
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def test_profile_documents_and_ownership(client):
    http, engine = client
    assert http.get(f"{API}/resumes").status_code == 401
    register(http, "ana@example.com")
    assert http.patch(API, json={"nickname": "  Anita  "}).json()["nickname"] == "Anita"
    assert http.get("/api/v1/auth/me").json()["nickname"] == "Anita"
    assert http.patch(API, json={"nickname": "   "}).status_code == 422
    first = http.post(f"{API}/resumes", files={"file": ("primero.pdf", pdf(), "application/pdf")})
    second = http.post(f"{API}/resumes", files={"file": ("segundo.pdf", pdf(), "application/pdf")})
    assert first.status_code == second.status_code == 201
    assert first.json()["is_primary"] is True
    assert second.json()["is_primary"] is False
    assert http.patch(f"{API}/resumes/{second.json()['id']}/primary").json()["is_primary"] is True
    assert [r["is_primary"] for r in http.get(f"{API}/resumes").json()] == [True, False]
    with Session(engine) as db:
        keys = db.scalars(select(Resume.storage_key)).all()
        assert len(set(keys)) == 2
        assert all(key.startswith("files/") and Path(settings.media_dir / key).is_file() for key in keys)
    assert http.get(f"{API}/resumes/{first.json()['id']}/download").content == pdf()
    register(http, "otra@example.com")
    assert http.get(f"{API}/resumes").json() == []
    assert http.get(f"{API}/resumes/{first.json()['id']}/download").status_code == 404
    assert http.patch(f"{API}/resumes/{first.json()['id']}/primary").status_code == 404


def test_hide_resume_requires_owner_preserves_file_and_promotes_primary(client):
    http, engine = client
    assert http.patch(f"{API}/resumes/1/hide").status_code == 401
    register(http, "ana@example.com")
    uploaded = [http.post(f"{API}/resumes", files={"file": (f"cv-{i}.pdf", pdf(),
                                                        "application/pdf")}).json()
                for i in range(3)]
    first, second, third = uploaded
    assert http.patch(f"{API}/resumes/{second['id']}/primary").status_code == 200
    with Session(engine) as db:
        original = db.get(Resume, second["id"])
        path = settings.media_dir / original.storage_key
    register(http, "otra@example.com")
    assert http.patch(f"{API}/resumes/{second['id']}/hide").status_code == 404
    assert http.get(f"{API}/resumes/{second['id']}/download").status_code == 404
    assert http.post("/api/v1/auth/login", json={
        "email": "ana@example.com", "password": "ClaveSegura1!",
    }).status_code == 200

    assert http.patch(f"{API}/resumes/{second['id']}/hide").status_code == 204
    listed = http.get(f"{API}/resumes").json()
    assert [item["id"] for item in listed] == [third["id"], first["id"]]
    assert [item["is_primary"] for item in listed] == [True, False]
    assert http.patch(f"{API}/resumes/{second['id']}/primary").status_code == 404
    assert http.get(f"{API}/resumes/{second['id']}/download").status_code == 404
    assert http.patch(f"{API}/resumes/{second['id']}/hide").status_code == 404
    assert path.is_file()
    with Session(engine) as db:
        hidden = db.get(Resume, second["id"])
        assert hidden.active is False
        assert hidden.is_primary is False

    assert http.patch(f"{API}/resumes/{first['id']}/hide").status_code == 204
    assert http.get(f"{API}/resumes").json()[0]["is_primary"] is True
    assert http.patch(f"{API}/resumes/{third['id']}/hide").status_code == 204
    assert http.get(f"{API}/resumes").json() == []
    replacement = http.post(f"{API}/resumes", files={"file": ("nuevo.pdf", pdf(),
                                                          "application/pdf")})
    assert replacement.json()["is_primary"] is True


def test_file_validation_and_avatar(client):
    http, _ = client
    register(http, "ana@example.com")
    for name, content, mime in [
        ("falso.pdf", b"%PDF-falso\n%%EOF", "application/pdf"),
        ("falso.txt", pdf(), "application/pdf"),
        ("grande.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf"),
    ]:
        assert http.post(f"{API}/resumes", files={"file": (name, content, mime)}).status_code == 422
    assert http.post(f"{API}/avatar", files={"file": ("imagen.webp", b"fake", "image/webp")}).status_code == 422
    image = io.BytesIO()
    Image.new("RGB", (256, 256), "red").save(image, format="PNG")
    saved = http.post(f"{API}/avatar", files={"file": ("foto.png", image.getvalue(), "image/png")})
    assert saved.status_code == 200
    assert saved.json()["avatar_url"]
    assert http.get(saved.json()["avatar_url"]).headers["content-type"] == "image/webp"
    assert len(list((settings.media_dir / "images").rglob("*.webp"))) == 1
    register(http, "otra@example.com")
    assert http.get("/api/v1/profile/avatar").status_code == 404
    assert http.get(saved.json()["avatar_url"]).status_code == 404
    assert http.post(f"{API}/resumes", files={"file": ("a.pdf", pdf(), "application/pdf")},
                     headers={"Origin": "https://otro.example"}).status_code == 403
