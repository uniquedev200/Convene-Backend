"""Hand-rolled email + password authentication.

No Supabase Auth, no third-party auth provider. Passwords are bcrypt-hashed,
JWTs are signed with our own secret.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Annotated

import bcrypt
import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from .storage import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-process)
# ---------------------------------------------------------------------------

_SIGNUP_ATTEMPTS: dict[str, list[float]] = {}

_SIGNUP_RATE_LIMIT = int(os.getenv("SIGNUP_RATE_LIMIT", "3"))       # signups per window
_SIGNUP_RATE_WINDOW = int(os.getenv("SIGNUP_RATE_WINDOW", "3600"))  # window in seconds (1 hour)


def _check_signup_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - _SIGNUP_RATE_WINDOW
    bucket = [t for t in _SIGNUP_ATTEMPTS.get(ip, []) if t >= window_start]
    if len(bucket) >= _SIGNUP_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many signups from this IP. Try again later.")
    bucket.append(now)
    _SIGNUP_ATTEMPTS[ip] = bucket

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is None:
        _jwt_secret = os.getenv("JWT_SECRET", "")
    return _jwt_secret


def _jwt_expiry_hours() -> int:
    return int(os.getenv("JWT_EXPIRY_HOURS", "72"))


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def issue_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + _jwt_expiry_hours() * 3600,
        "iat": int(time.time()),
    }
    return pyjwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def _decode_token(token: str) -> dict:
    return pyjwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, request: Request) -> AuthResponse:
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not available")

    existing = await pool.fetchval(
        "SELECT id FROM users WHERE email = $1", body.email
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(body.password)
    await pool.execute(
        """
        INSERT INTO users (id, email, password_hash, verified, created_at)
        VALUES ($1, $2, $3, true, now())
        """,
        user_id,
        body.email,
        pw_hash,
    )

    token = issue_token(user_id)
    return AuthResponse(access_token=token, user_id=user_id)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not available")

    row = await pool.fetchrow(
        "SELECT id, password_hash FROM users WHERE email = $1",
        body.email,
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = issue_token(str(row["id"]))
    return AuthResponse(access_token=token, user_id=str(row["id"]))


# ---------------------------------------------------------------------------
# Dependency for route protection (unchanged shape)
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract and verify JWT from Authorization header.

    Returns the user_id (sub claim) on success, or None if no token is
    provided (anonymous request). Raises 401 if a token is provided but
    invalid or expired.
    """
    if authorization is None:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]

    secret = _get_jwt_secret()
    if not secret:
        logger.error("JWT_SECRET is not set")
        raise HTTPException(status_code=500, detail="Auth not configured")

    try:
        payload = _decode_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        return user_id
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as exc:
        logger.warning("Invalid token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")


class OAuthExchangeRequest(BaseModel):
    access_token: str


async def verify_supabase_token(token: str) -> dict | None:
    supabase_url = os.getenv("SUPABASE_URL", "https://zxnfcbojuxbdqzryqtaw.supabase.co")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_myU9f34KZ5iNyLiKet5-cQ_y0xc0_PC")
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": supabase_key
    }
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{supabase_url}/auth/v1/user", headers=headers, timeout=5.0)
            if res.status_code == 200:
                return res.json()
            else:
                logger.error("Supabase user verification returned status %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.error("Supabase user verification failed: %s", e)
    return None


@router.post("/oauth-exchange", response_model=AuthResponse)
async def oauth_exchange(body: OAuthExchangeRequest) -> AuthResponse:
    pool = await get_pool()

    user_info = await verify_supabase_token(body.access_token)
    if user_info is None:
        raise HTTPException(status_code=401, detail="Invalid Supabase OAuth token")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Missing email in OAuth profile")

    if pool is not None:
        row = await pool.fetchrow(
            "SELECT id FROM users WHERE email = $1", email
        )
        if row is None:
            user_id = str(uuid.uuid4())
            await pool.execute(
                """
                INSERT INTO users (id, email, password_hash, verified, created_at)
                VALUES ($1, $2, $3, true, now())
                """,
                user_id,
                email,
                "",
            )
        else:
            user_id = str(row["id"])
    else:
        # Fallback: Deterministic UUID based on email when database is offline
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))

    token = issue_token(user_id)
    return AuthResponse(access_token=token, user_id=user_id)
