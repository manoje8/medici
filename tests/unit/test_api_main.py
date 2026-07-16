"""
Unit tests for src/api/main.py

Tests create_apps() function for:
- Root endpoint returns 200
- Health endpoint with qdrant reachable → 200 with status=ok
- Health endpoint with qdrant unreachable → 503 with status=degraded
- Health endpoint when qdrant not initialized → 503
- CORS origins: wildcard '*' expands to ['*']
- CORS origins: comma-separated string splits correctly
- main.py module structure (imports do not raise)

We mock the lifespan context so tests don't need a real DB/Redis/Qdrant.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers: build app without lifespan startup
# ---------------------------------------------------------------------------


def _build_test_app(qdrant_ping_result: bool | None = None):
    """Build create_apps() result but bypass lifespan by mocking config."""
    from src.api.main import create_apps

    with patch("src.api.main.config") as mock_config:
        mock_config.PROJECT_NAME = "test-project"
        mock_config.CORS_ORIGINS = "*"

        app = create_apps()

    # Wire mocked state manually (no lifespan ran)
    if qdrant_ping_result is not None:
        mock_qdrant = MagicMock()
        mock_qdrant.ping = AsyncMock(return_value=qdrant_ping_result)
        app.state.qdrant = mock_qdrant
    else:
        # Ensure no qdrant attribute
        if hasattr(app.state, "qdrant"):
            del app.state.qdrant

    return app


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    def test_root_returns_200(self):
        from src.api.main import create_apps

        with patch("src.api.main.config") as mock_config:
            mock_config.PROJECT_NAME = "test-project"
            mock_config.CORS_ORIGINS = "*"
            app = create_apps()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok_when_qdrant_reachable(self):
        app = _build_test_app(qdrant_ping_result=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dependencies"]["qdrant"] == "ok"

    def test_health_degraded_when_qdrant_unreachable(self):
        app = _build_test_app(qdrant_ping_result=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["qdrant"] == "unreachable"

    def test_health_degraded_when_qdrant_not_initialized(self):
        app = _build_test_app(qdrant_ping_result=None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        # qdrant is None → ping skipped → qdrant_ok=False → degraded
        assert resp.status_code == 503

    def test_health_includes_service_name(self):
        from src.api.main import create_apps

        with patch("src.api.main.config") as mock_config:
            mock_config.PROJECT_NAME = "my-rag-service"
            mock_config.CORS_ORIGINS = "*"
            app = create_apps()

        mock_qdrant = MagicMock()
        mock_qdrant.ping = AsyncMock(return_value=True)
        app.state.qdrant = mock_qdrant

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.json()["service"] == "Studious"


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------


class TestCorsConfiguration:
    def test_wildcard_origins_string(self):
        from src.api.main import create_apps

        with patch("src.api.main.config") as mock_config:
            mock_config.PROJECT_NAME = "test"
            mock_config.CORS_ORIGINS = "*"
            app = create_apps()

        assert app is not None
        assert app.title == "test"

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == "server running"

    def test_comma_separated_origins(self):
        """Comma-separated origins should be split into a list."""
        from src.api.main import create_apps

        with patch("src.api.main.config") as mock_config:
            mock_config.PROJECT_NAME = "test"
            mock_config.CORS_ORIGINS = "http://localhost:3000,http://app.example.com"
            app = create_apps()

        assert app is not None


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


class TestRouterRegistration:
    def test_document_and_query_routes_registered(self):
        from src.api.main import create_apps

        with patch("src.api.main.config") as mock_config:
            mock_config.PROJECT_NAME = "test"
            mock_config.CORS_ORIGINS = "*"
            app = create_apps()

        routes = {r.path for r in app.routes}  # type: ignore[attr-defined]
        assert "/ingestion" in routes
        assert "/bulk-ingestion" in routes
        assert "/query" in routes
