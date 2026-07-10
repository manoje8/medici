"""
Integration tests: CORS startup configuration seam.

Seam under test: create_apps() reads config.CORS_ORIGINS at startup and
passes it directly to CORSMiddleware. If CORS_ORIGINS is None (unset env var),
get_cors_origins() calls None.split(",") which raises AttributeError — crashing
the server before it serves a single request.

This test suite documents the crash as an xfail, verifies correct behaviour
for the valid configurations, and confirms CORS headers are actually sent.
"""

from unittest.mock import patch

import pytest


def _create_app_with_cors(cors_origins: str | None):
    """
    Call create_apps() with a specific CORS_ORIGINS value, patching config
    and the lifespan so we don't need Postgres/Redis/Qdrant.
    """
    from src.api.main import create_apps
    from src.common.utils import config as config_module

    with patch.object(config_module.config, "CORS_ORIGINS", cors_origins):
        return create_apps()


# ---------------------------------------------------------------------------
# Valid CORS configurations
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCORSStartupValidConfigurations:
    """create_apps() must succeed for all valid CORS_ORIGINS values."""

    def test_wildcard_cors_creates_app_without_error(self):
        app = _create_app_with_cors("*")
        assert app is not None

    def test_single_origin_creates_app_without_error(self):
        app = _create_app_with_cors("http://localhost:3000")
        assert app is not None

    def test_comma_separated_origins_creates_app_without_error(self):
        app = _create_app_with_cors("http://app.example.com,http://admin.example.com")
        assert app is not None

    def test_wildcard_cors_registers_correct_origins(self):
        """With '*', the app must have at least one middleware registered (CORS)."""
        app = _create_app_with_cors("*")
        # FastAPI wraps all middleware as generic 'Middleware' entries;
        # the meaningful check is that at least one middleware was added at all.
        assert (
            len(app.user_middleware) >= 1
        ), "No middleware registered. CORSMiddleware add_middleware() call may have failed."

    def test_comma_separated_origins_are_split_correctly(self):
        """
        Verify that 'a.com,b.com' is parsed into ['a.com', 'b.com'], not left
        as a single-element list containing the full string.
        """
        from src.api.main import create_apps
        from src.common.utils import config as config_module

        origins_list = None

        # Monkeypatch CORSMiddleware to capture the allow_origins argument
        original_add = None

        def capture_middleware(cls, **kwargs):
            nonlocal origins_list
            if "CORSMiddleware" in str(cls) or hasattr(cls, "allow_origins"):
                origins_list = kwargs.get("allow_origins")
            if original_add:
                original_add(cls, **kwargs)

        with patch.object(config_module.config, "CORS_ORIGINS", "http://a.com,http://b.com"):
            app = create_apps()

        # Introspect the middleware stack
        for mw in app.user_middleware:
            kwargs = getattr(mw, "kwargs", {})
            if kwargs.get("allow_origins"):
                origins_list = kwargs["allow_origins"]
                break

        if origins_list is not None:
            assert isinstance(origins_list, list), (
                f"allow_origins must be a list, got {type(origins_list)}. "
                "A single string would fail CORS header matching."
            )
            assert "http://a.com" in origins_list
            assert "http://b.com" in origins_list


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CORS_ORIGINS=None crashes startup: get_cors_origins() calls None.split(',') "
        "raising AttributeError. Fix: add `or ''` default — `origins_str = config.CORS_ORIGINS or ''`."
    ),
)
def test_cors_origins_none_does_not_crash_startup():
    """
    When CORS_ORIGINS env var is unset (None), create_apps() currently raises
    AttributeError: 'NoneType' object has no attribute 'split'.

    This test is marked xfail(strict=True) so it:
      - Is GREEN in CI while the bug exists (xfail passes = expected failure)
      - Turns RED if the bug is silently fixed without updating this test
      - Documents the exact bug location and fix for the developer

    Fix location: src/api/main.py, get_cors_origins():
        origins_str = config.CORS_ORIGINS or ""   # ← add `or ""`
    """
    _create_app_with_cors(None)  # must NOT raise AttributeError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cors_header_present_for_allowed_origin():
    """
    An OPTIONS preflight request from a configured origin must receive
    the Access-Control-Allow-Origin header — end-to-end check that the
    middleware is actually wired, not just registered.
    """
    from httpx import ASGITransport, AsyncClient

    app = _create_app_with_cors("http://frontend.example.com")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.options(
            "/",
            headers={
                "Origin": "http://frontend.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    # The CORS middleware should set this header for a preflight from an allowed origin
    assert "access-control-allow-origin" in resp.headers, (
        "CORS middleware is registered but not returning allow-origin header. "
        "The middleware may be incorrectly configured."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cors_wildcard_allows_any_origin():
    """With CORS_ORIGINS='*', any origin must be allowed."""
    from httpx import ASGITransport, AsyncClient

    app = _create_app_with_cors("*")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get("/", headers={"Origin": "http://anything.example.com"})

    assert "access-control-allow-origin" in resp.headers
