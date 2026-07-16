from datetime import UTC, datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status
from pydantic import BaseModel

from src.api.config_api import config_api

HASH_PREFIX = "{bcrypt}"


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    role: str = "user"
    metadata: dict = {}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hash_pass = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    return f"{HASH_PREFIX}{hash_pass}"


def verify_password(plain_password: str, stored_password: str) -> bool:
    if stored_password.startswith(HASH_PREFIX):
        hash_pass = stored_password[len(HASH_PREFIX) :]
        if not hash_pass:
            return False

        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hash_pass.encode("utf-8"))
        except ValueError:
            return False

    return plain_password == stored_password


def create_access_token(
    user_name: str, role: str = "user", expire_hours: int = None, metadata: dict = None
) -> str:
    if not expire_hours:
        expire_hours = 5
    expire = datetime.now(UTC) + timedelta(hours=expire_hours)
    payload = TokenPayload(sub=user_name, role=role, exp=expire, metadata=metadata or {})

    return jwt.encode(payload.model_dump(), config_api.SECRET_KEY, config_api.ALGORITHM)


def validate_token(token: str) -> dict:
    try:
        if config_api.ALGORITHM is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid JWT algorithm"
            )

        payload = jwt.decode(token, config_api.SECRET_KEY, config_api.ALGORITHM)
        expire_timestamp = payload["exp"]
        expire_time = datetime.fromtimestamp(expire_timestamp, timezone.utc)

        if datetime.now(UTC) > expire_time:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

        return {
            "user_name": payload["sub"],
            "role": payload["role"],
            "metadata": payload["metadata"],
            "exp": expire_time,
        }
    except jwt.exceptions.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from err
