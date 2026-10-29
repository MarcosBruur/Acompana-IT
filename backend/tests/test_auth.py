import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Candidate, CandidateSession, GoogleIdentity
from app.main import app
from app.modules.auth.router import db_session, hasher

API = "/api/v1/auth"
PASSWORD = "ClaveSegura1!"


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__, CandidateSession.__table__, GoogleIdentity.__table__])

    def test_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[db_session] = test_session
    with TestClient(app, base_url="http://localhost:8000", headers={"Origin": "http://localhost:5173"}) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email="persona@example.com"):
    http, _ = client
    return http.post(f"{API}/register", json={
        "email": email, "first_name": "Ana", "last_name": "Pérez",
        "password": PASSWORD, "confirm_password": PASSWORD,
    })


def test_register_login_logout_and_hash(client):
    http, engine = client
    response = register(client)
    assert response.status_code == 201
    assert response.json()["role"] == "candidato"
    assert response.json()["id"] == 1
    assert response.json()["password_expired"] is False
    with Session(engine) as db:
        saved = db.scalar(select(Candidate))
        assert saved.password_hash != PASSWORD
        assert hasher.verify(saved.password_hash, PASSWORD)
        assert db.scalar(select(CandidateSession)).token_hash != http.cookies["candidate_session"]

    assert register(client).status_code == 409
    assert http.get(f"{API}/me").json()["email"] == "persona@example.com"
    assert http.post(f"{API}/logout").status_code == 204
    assert http.get(f"{API}/me").status_code == 401
    assert http.post(f"{API}/login", json={"email": "persona@example.com", "password": "wrong"}).status_code == 401
    assert http.post(f"{API}/login", json={"email": "PERSONA@example.com", "password": PASSWORD}).status_code == 200


def test_ids_are_incremental_and_foreign_keys_use_integers(client):
    _, engine = client
    first = register(client, "primera@example.com")
    second = register(client, "segunda@example.com")
    assert (first.json()["id"], second.json()["id"]) == (1, 2)
    with Session(engine) as db:
        sessions = db.scalars(select(CandidateSession).order_by(CandidateSession.id)).all()
        assert [session.id for session in sessions] == [1, 2]
        assert [session.candidate_id for session in sessions] == [1, 2]


@pytest.mark.parametrize("password", ["Corta1!", "minuscula1!", "SinNumero!", "SinEspecial1"])
def test_password_rules(client, password):
    http, _ = client
    assert http.post(f"{API}/register", json={
        "email": "a@example.com", "first_name": "Ana", "last_name": "B",
        "password": password, "confirm_password": password,
    }).status_code == 422


def test_register_requires_matching_confirmation(client):
    http, engine = client
    payload = {
        "email": "a@example.com", "first_name": "Ana", "last_name": "B",
        "password": PASSWORD, "confirm_password": "OtraClave2!",
    }
    response = http.post(f"{API}/register", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "confirm_password"
    with Session(engine) as db:
        assert db.scalar(select(Candidate)) is None
    del payload["confirm_password"]
    assert http.post(f"{API}/register", json=payload).status_code == 422


def test_expiry_and_renewal_revokes_other_sessions(client):
    http, engine = client
    register(client)
    old_token = http.cookies["candidate_session"]
    with Session(engine) as db:
        candidate = db.scalar(select(Candidate))
        candidate.password_changed_at = datetime.now(UTC) - timedelta(days=200)
        db.commit()
    assert http.get(f"{API}/me").json()["password_expired"] is True
    assert http.post(f"{API}/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD, "confirm_password": PASSWORD}).status_code == 422
    assert http.post(f"{API}/change-password", json={"current_password": "wrong", "new_password": "OtraClave2!", "confirm_password": "OtraClave2!"}).status_code == 401
    changed = http.post(f"{API}/change-password", json={"current_password": PASSWORD, "new_password": "OtraClave2!", "confirm_password": "OtraClave2!"})
    assert changed.status_code == 200
    assert changed.json()["password_expired"] is False
    with Session(engine) as db:
        assert db.scalar(select(CandidateSession).where(CandidateSession.token_hash == hashlib.sha256(old_token.encode()).hexdigest())) is None
    assert http.post(f"{API}/logout").status_code == 204
    assert http.post(f"{API}/login", json={"email": "persona@example.com", "password": PASSWORD}).status_code == 401
    assert http.post(f"{API}/login", json={"email": "persona@example.com", "password": "OtraClave2!"}).status_code == 200


def test_password_change_requires_matching_confirmation(client):
    http, engine = client
    register(client)
    payload = {
        "current_password": PASSWORD, "new_password": "OtraClave2!",
        "confirm_password": "NoCoincide3!",
    }
    response = http.post(f"{API}/change-password", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "confirm_password"
    with Session(engine) as db:
        assert hasher.verify(db.scalar(select(Candidate)).password_hash, PASSWORD)
    del payload["confirm_password"]
    assert http.post(f"{API}/change-password", json=payload).status_code == 422


def test_reject_untrusted_origin_and_session_expiry(client):
    http, engine = client
    assert http.post(f"{API}/register", headers={"Origin": "https://otro.example"}, json={
        "email": "a@example.com", "first_name": "Ana", "last_name": "B",
        "password": PASSWORD, "confirm_password": PASSWORD,
    }).status_code == 403
    register(client)
    with Session(engine) as db:
        session = db.scalar(select(CandidateSession))
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert http.get(f"{API}/me").status_code == 401


def test_google_requires_configuration(client, monkeypatch):
    from app.core.config import settings

    http, _ = client
    monkeypatch.setattr(settings, "google_client_id", None)
    monkeypatch.setattr(settings, "google_client_secret", None)
    assert http.get(f"{API}/google/available").json() == {"available": False}
    assert http.get(f"{API}/google").status_code == 503


def test_google_oauth_callback(client, monkeypatch):
    from app.core.config import settings
    from app.modules.auth import router as auth_router

    http, engine = client
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "secret")

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class FakeGoogle:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            assert data["code_verifier"]
            return FakeResponse({"access_token": "google-token"})

        async def get(self, url, headers):
            assert headers["Authorization"] == "Bearer google-token"
            return FakeResponse({
                "sub": "google-123", "email": "google@example.com", "email_verified": True,
                "given_name": "Luz", "family_name": "García",
            })

    monkeypatch.setattr(auth_router.httpx, "AsyncClient", FakeGoogle)
    start = http.get(f"{API}/google", follow_redirects=False)
    assert start.status_code == 307
    assert "code_challenge=" in start.headers["location"]
    assert http.get(f"{API}/google/callback?state=invalid&code=abc", follow_redirects=False).headers["location"].endswith("google_error=1")
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    callback = http.get(f"{API}/google/callback?state={state}&code=abc", follow_redirects=False)
    assert callback.status_code == 307
    assert http.get(f"{API}/me").json()["first_name"] == "Luz"
    with Session(engine) as db:
        assert db.scalar(select(GoogleIdentity)).google_sub == "google-123"
        assert db.scalar(select(Candidate)).password_hash is None


def test_google_does_not_link_existing_local_account(client, monkeypatch):
    from app.core.config import settings
    from app.modules.auth import router as auth_router

    http, engine = client
    register(client, "google@example.com")
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "secret")

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class FakeGoogle:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            return FakeResponse({"access_token": "access"})

        async def get(self, url, headers):
            return FakeResponse({"sub": "another-sub", "email": "google@example.com", "email_verified": True})

    monkeypatch.setattr(auth_router.httpx, "AsyncClient", FakeGoogle)
    start = http.get(f"{API}/google", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    callback = http.get(f"{API}/google/callback?state={state}&code=abc", follow_redirects=False)
    assert callback.headers["location"].endswith("google_error=linked")
    with Session(engine) as db:
        assert db.scalar(select(GoogleIdentity)) is None
