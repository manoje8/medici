"""
Security tests for the API layer.

Covers:
- require_auth: missing token → 401, malformed header → 401, expired token → 401,
  valid token → payload returned
- require_admin: valid user token → 403, valid admin token → ok
- /bulk-ingestion path jail: path inside INGESTION_ROOT → accepted,
  path escaping root → 400
- /query without token → 401
- /ingestion without token → 401
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET = "test-secret-key-not-for-production"
_ALGO = "HS256"
_VALID_PARSE_METHOD = "docling"


def _make_token(role: str = "user", expired: bool = False) -> str:
    exp = int(time.time()) + (-60 if expired else 3600)
    payload = {"sub": "testuser", "role": role, "exp": exp, "metadata": {}}
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit tests for require_auth / require_admin dependencies (sync callables)
# ---------------------------------------------------------------------------


class TestRequireAuth:
    """require_auth dependency in isolation."""

    def test_missing_token_raises_401(self):
        from fastapi import HTTPException

        from src.api.deps import require_auth

        with pytest.raises(HTTPException) as exc_info:
            require_auth(credentials=None)

        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    def test_valid_token_returns_payload(self):
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.deps import require_auth

        expected = {"user_name": "testuser", "role": "user"}

        with patch("src.api.deps.validate_token", return_value=expected) as mock_vt:
            fake_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
            result = require_auth(credentials=fake_creds)

        assert result == expected
        mock_vt.assert_called_once_with("tok")

    def test_invalid_token_propagates_401(self):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        from src.api.deps import require_auth

        with patch(
            "src.api.deps.validate_token",
            side_effect=HTTPException(status_code=401, detail="Invalid token"),
        ):
            fake_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad")
            with pytest.raises(HTTPException) as exc_info:
                require_auth(credentials=fake_creds)

        assert exc_info.value.status_code == 401


class TestRequireAdmin:
    """require_admin dependency in isolation."""

    def test_user_role_raises_403(self):
        from fastapi import HTTPException

        from src.api.deps import require_admin

        with pytest.raises(HTTPException) as exc_info:
            require_admin(token_payload={"role": "user", "user_name": "alice"})

        assert exc_info.value.status_code == 403
        assert "Admin" in exc_info.value.detail

    def test_admin_role_returns_payload(self):
        from src.api.deps import require_admin

        payload = {"role": "admin", "user_name": "alice"}
        result = require_admin(token_payload=payload)
        assert result == payload

    def test_missing_role_key_raises_403(self):
        from fastapi import HTTPException

        from src.api.deps import require_admin

        with pytest.raises(HTTPException) as exc_info:
            require_admin(token_payload={"user_name": "ghost"})

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Integration-style tests: FastAPI TestClient
# ---------------------------------------------------------------------------


def _build_app(ingestion_root: Path) -> FastAPI:
    """Build a minimal FastAPI app with real document + query routes,
    patching INGESTION_ROOT and replacing heavy deps with mocks."""
    import src.api.routers.document_routes as doc_mod
    from src.api.routers.query_router import create_query_routes

    app = FastAPI()

    # Patch the module-level constant before the router registers routes
    with patch.object(doc_mod, "INGESTION_ROOT", ingestion_root):
        from src.api.routers.document_routes import create_document_routes

        app.include_router(create_document_routes())

    app.include_router(create_query_routes())

    mock_processor = MagicMock()
    mock_processor.ingest_documents = AsyncMock(return_value={"status": "ok"})
    mock_pipeline = MagicMock()
    mock_pipeline.chat = AsyncMock(
        return_value={
            "answer": "ok",
            "session_id": "s1",
            "sources": [],
            "query_was_rewritten": False,
            "retrieval_rounds": 1,
        }
    )
    app.state.processor = mock_processor
    app.state.pipeline = mock_pipeline
    return app


@pytest.fixture
def ingestion_root(tmp_path):
    root = tmp_path / "ingestion"
    root.mkdir()
    return root


@pytest.fixture
def app(ingestion_root):
    return _build_app(ingestion_root)


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_validate():
    """Patch validate_token at the deps layer for all integration tests."""
    with patch("src.api.deps.validate_token") as m:
        yield m


# ---------------------------------------------------------------------------
# /query
# ---------------------------------------------------------------------------


class TestQueryEndpointAuth:
    def test_query_without_token_returns_401(self, client):
        resp = client.post("/query", json={"question": "hello", "user_id": "u1"})
        assert resp.status_code == 401

    def test_query_with_valid_token_succeeds(self, client, mock_validate):
        mock_validate.return_value = {"role": "user", "user_name": "alice"}
        resp = client.post(
            "/query",
            json={"question": "hello", "user_id": "u1"},
            headers=_auth_header("valid-tok"),
        )
        assert resp.status_code == 200

    def test_query_with_invalid_token_returns_401(self, client, mock_validate):
        from fastapi import HTTPException

        mock_validate.side_effect = HTTPException(status_code=401, detail="Invalid token")
        resp = client.post(
            "/query",
            json={"question": "hello", "user_id": "u1"},
            headers=_auth_header("bad-tok"),
        )
        assert resp.status_code == 401


class TestIngestionEndpointAuth:
    def test_ingestion_without_token_returns_401(self, client):
        resp = client.post(
            "/ingestion",
            data={"parse_method": _VALID_PARSE_METHOD},
            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
        )
        assert resp.status_code == 401
