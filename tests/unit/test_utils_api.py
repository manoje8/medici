"""
Unit tests for API utility functions (src/api/utils_api.py).

No real JWT secret from config is needed — we patch config_api where required.
Covers:
- hash_password: produces bcrypt hash with prefix
- verify_password: correct plain password accepted, wrong rejected
- verify_password: handles stored password without prefix (plain text fallback)
- verify_password: handles empty hash_pass gracefully
- create_access_token: token is decodable and contains expected payload
- validate_token: valid token returns user payload
- validate_token: expired token raises HTTP 401
- validate_token: tampered/invalid token raises HTTP 401
- validate_token: None algorithm raises HTTP 500
- TokenPayload model field defaults
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Patch config_api before importing utils_api
# ---------------------------------------------------------------------------

_SECRET = "super-secret-test-key-for-testing-only"
_ALGO = "HS256"


@pytest.fixture(autouse=True)
def patch_config_api():
    with patch("src.api.utils_api.config_api") as mock_cfg:
        mock_cfg.SECRET_KEY = _SECRET
        mock_cfg.ALGORITHM = _ALGO
        yield mock_cfg


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_hash_password_returns_string_with_bcrypt_prefix(self):
        from src.api.utils_api import HASH_PREFIX, hash_password

        result = hash_password("mysecret")
        assert isinstance(result, str)
        assert result.startswith(HASH_PREFIX)

    def test_hash_password_different_salts_for_same_input(self):
        from src.api.utils_api import hash_password

        h1 = hash_password("mysecret")
        h2 = hash_password("mysecret")
        assert h1 != h2  # bcrypt uses random salt

    def test_hash_password_non_empty_result(self):
        from src.api.utils_api import hash_password

        assert len(hash_password("any-password")) > 10


class TestVerifyPassword:
    def test_correct_password_verified(self):
        from src.api.utils_api import hash_password, verify_password

        hashed = hash_password("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_wrong_password_rejected(self):
        from src.api.utils_api import hash_password, verify_password

        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_plain_text_fallback_when_no_prefix(self):
        from src.api.utils_api import verify_password

        # Stored password without prefix — plain text comparison
        assert verify_password("plain", "plain") is True
        assert verify_password("plain", "other") is False

    def test_empty_bcrypt_hash_returns_false(self):
        from src.api.utils_api import HASH_PREFIX, verify_password

        # Prefix present but hash portion is empty
        assert verify_password("anything", HASH_PREFIX) is False

    def test_corrupted_bcrypt_hash_returns_false(self):
        from src.api.utils_api import HASH_PREFIX, verify_password

        # Not a valid bcrypt hash
        assert verify_password("anything", f"{HASH_PREFIX}notabcrypthash") is False


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_token_is_decodable_with_secret(self):
        from src.api.utils_api import create_access_token

        token = create_access_token("alice", role="user")
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        assert payload["sub"] == "alice"
        assert payload["role"] == "user"

    def test_token_has_future_expiry(self):
        from src.api.utils_api import create_access_token

        token = create_access_token("bob", expire_hours=1)
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        assert payload["exp"] > time.time()

    def test_custom_role_in_token(self):
        from src.api.utils_api import create_access_token

        token = create_access_token("admin-user", role="admin")
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        assert payload["role"] == "admin"

    def test_default_expire_hours_used_when_none(self):
        from src.api.utils_api import create_access_token

        token = create_access_token("charlie")
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        # Default is 5 hours; exp should be roughly now + 5h
        expected_max = time.time() + 5 * 3600 + 60
        assert payload["exp"] <= expected_max

    def test_metadata_included_in_token(self):
        from src.api.utils_api import create_access_token

        token = create_access_token("dave", metadata={"tenant": "acme"})
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        assert payload["metadata"]["tenant"] == "acme"


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------


class TestValidateToken:
    def _make_token(self, sub="alice", role="user", exp_delta_hours=1, metadata=None):
        exp = datetime.now(UTC) + timedelta(hours=exp_delta_hours)
        payload = {
            "sub": sub,
            "role": role,
            "exp": exp,
            "metadata": metadata or {},
        }
        return jwt.encode(payload, _SECRET, algorithm=_ALGO)

    def test_valid_token_returns_user_payload(self):
        from src.api.utils_api import validate_token

        token = self._make_token("alice", "user")
        result = validate_token(token)
        assert result["user_name"] == "alice"
        assert result["role"] == "user"

    def test_valid_admin_token_returns_admin_role(self):
        from src.api.utils_api import validate_token

        token = self._make_token("root", "admin")
        result = validate_token(token)
        assert result["role"] == "admin"

    def test_expired_token_raises_401(self):
        from src.api.utils_api import validate_token

        token = self._make_token(exp_delta_hours=-1)  # expired 1 hour ago
        with pytest.raises(HTTPException) as exc_info:
            validate_token(token)
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self):
        from src.api.utils_api import validate_token

        with pytest.raises(HTTPException) as exc_info:
            validate_token("this.is.not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self):
        from src.api.utils_api import validate_token

        token = jwt.encode(
            {"sub": "x", "role": "user", "exp": time.time() + 3600, "metadata": {}},
            "wrong-secret",
            algorithm=_ALGO,
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_token(token)
        assert exc_info.value.status_code == 401

    def test_none_algorithm_raises_500(self, patch_config_api):
        from src.api.utils_api import validate_token

        patch_config_api.ALGORITHM = None
        with pytest.raises(HTTPException) as exc_info:
            validate_token("any-token")
        assert exc_info.value.status_code == 500

    def test_result_contains_exp_datetime(self):
        from src.api.utils_api import validate_token

        token = self._make_token()
        result = validate_token(token)
        assert isinstance(result["exp"], datetime)


# ---------------------------------------------------------------------------
# TokenPayload model
# ---------------------------------------------------------------------------


class TestTokenPayload:
    def test_token_payload_defaults(self):
        from src.api.utils_api import TokenPayload

        now = datetime.now(UTC) + timedelta(hours=1)
        tp = TokenPayload(sub="user1", exp=now)
        assert tp.role == "user"
        assert tp.metadata == {}

    def test_token_payload_custom_role(self):
        from src.api.utils_api import TokenPayload

        now = datetime.now(UTC) + timedelta(hours=1)
        tp = TokenPayload(sub="admin", exp=now, role="admin")
        assert tp.role == "admin"
