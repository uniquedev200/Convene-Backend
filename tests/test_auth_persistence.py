"""Tests for hand-rolled auth, persistence, and access control."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.contracts import DOMAIN_REGISTRY
from app.main import SESSIONS, app
from app import auth as auth_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_JWT_SECRET = "test-jwt-secret-unit-tests"


def _make_token(sub: str = "user-abc-123", exp: int | None = None) -> str:
    payload: dict[str, Any] = {"sub": sub}
    if exp is not None:
        payload["exp"] = exp
    else:
        payload["exp"] = int(time.time()) + 3600
    payload["iat"] = int(time.time())
    return jwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fake_pool() -> MagicMock:
    """Return a mock asyncpg pool that tracks in-memory state."""
    pool = MagicMock()
    pool._users: dict[str, dict] = {}  # email -> {id, password_hash, verified}
    pool._debates: dict[str, dict] = {}  # id -> row

    async def mock_fetchval(query, *args):
        email = args[0] if args else None
        if "FROM users WHERE email" in query and email:
            return pool._users.get(email, {}).get("id")
        return None

    async def mock_fetchrow(query, *args):
        if "INSERT INTO users" in query:
            return None
        email = args[0] if args else None
        if "SELECT id FROM users WHERE email" in query and email:
            u = pool._users.get(email)
            if u is None:
                return None
            return {"id": u["id"]}
        if "SELECT id, password_hash FROM users WHERE email" in query and email:
            u = pool._users.get(email)
            if u is None:
                return None
            return {"id": u["id"], "password_hash": u["password_hash"]}
        if "FROM debates WHERE id" in query:
            debate_id = args[0] if args else None
            return pool._debates.get(debate_id)
        return None

    async def mock_fetch(query, *args):
        if "FROM debates WHERE user_id" in query:
            uid = args[0] if args else None
            rows = [d for d in pool._debates.values() if d.get("user_id") == uid]
            rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return rows
        return []

    async def mock_execute(query, *args):
        if "INSERT INTO users" in query:
            uid, email, pw_hash = args[0], args[1], args[2]
            pool._users[email] = {"id": uid, "email": email, "password_hash": pw_hash, "verified": True}
        elif "INSERT INTO debates" in query:
            debate_id, uid, preset, question = args[0], args[1], args[2], args[3]
            import json
            options = json.loads(args[4]) if isinstance(args[4], str) else args[4]
            pool._debates[debate_id] = {"id": debate_id, "user_id": uid, "preset_id": preset, "question": question, "options": options, "status": "pending"}
        elif "UPDATE debates SET status" in query and "result" not in query:
            status, did = args[0], args[1]
            if did in pool._debates:
                pool._debates[did]["status"] = status
        elif "UPDATE debates SET status = 'complete'" in query:
            did = args[1]
            if did in pool._debates:
                pool._debates[did]["status"] = "complete"
        return "OK"

    pool.fetchval = mock_fetchval
    pool.fetchrow = mock_fetchrow
    pool.fetch = mock_fetch
    pool.execute = mock_execute
    return pool


# ---------------------------------------------------------------------------
# Auth: signup
# ---------------------------------------------------------------------------


class TestSignup:

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_signup_creates_verified_user_and_returns_token(self, _jwt_secret, mock_pool):
        pool = _fake_pool()
        mock_pool.return_value = pool
        client = TestClient(app)

        resp = client.post("/auth/signup", json={"email": "new@test.com", "password": "securepass1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user_id"]

        user = pool._users["new@test.com"]
        assert user["verified"] is True
        assert user["password_hash"] != "securepass1"

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_signup_duplicate_email_returns_409(self, _jwt_secret, mock_pool):
        pool = _fake_pool()
        pool._users["taken@test.com"] = {"id": "existing", "email": "taken@test.com", "password_hash": "x", "verified": True}
        mock_pool.return_value = pool
        client = TestClient(app)

        resp = client.post("/auth/signup", json={"email": "taken@test.com", "password": "securepass1"})
        assert resp.status_code == 409

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_signup_short_password_rejected(self, _jwt_secret, mock_pool):
        mock_pool.return_value = _fake_pool()
        client = TestClient(app)
        resp = client.post("/auth/signup", json={"email": "a@b.com", "password": "short"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth: login
# ---------------------------------------------------------------------------


class TestLogin:

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_login_user_succeeds(self, _jwt_secret, mock_pool):
        import bcrypt as bc
        pool = _fake_pool()
        mock_pool.return_value = pool
        pw_hash = bc.hashpw(b"mypassword", bc.gensalt()).decode()
        pool._users["login@test.com"] = {
            "id": "u-login", "email": "login@test.com",
            "password_hash": pw_hash, "verified": True,
        }

        client = TestClient(app)
        resp = client.post("/auth/login", json={"email": "login@test.com", "password": "mypassword"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user_id"] == "u-login"

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_login_wrong_password_fails(self, _jwt_secret, mock_pool):
        import bcrypt as bc
        pool = _fake_pool()
        mock_pool.return_value = pool
        pool._users["login2@test.com"] = {
            "id": "u-login2", "email": "login2@test.com",
            "password_hash": bc.hashpw(b"correct", bc.gensalt()).decode(),
            "verified": True,
        }

        client = TestClient(app)
        resp = client.post("/auth/login", json={"email": "login2@test.com", "password": "wrong"})
        assert resp.status_code == 401

    @patch("app.auth.get_pool")
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_login_unknown_email_fails(self, _jwt_secret, mock_pool):
        mock_pool.return_value = _fake_pool()
        client = TestClient(app)
        resp = client.post("/auth/login", json={"email": "ghost@test.com", "password": "pass1234"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------


class TestGetCurrentUser:

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_valid_token_sets_user_id_on_debate(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-auth-1")

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        session = SESSIONS[resp.json()["debate_id"]]
        assert session.user_id == "user-auth-1"

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_no_token_returns_401(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
        )
        assert resp.status_code == 401

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_invalid_token_returns_401(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_expired_token_returns_401(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-auth-2", exp=int(time.time()) - 3600)

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 401

    @patch("app.auth._get_jwt_secret", return_value="wrong-secret")
    def test_wrong_secret_returns_401(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-auth-3")

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 401

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_stream_works_after_authed_create(self, _jwt_secret):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-stream-1")
        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_auth_header(token),
        )
        debate_id = resp.json()["debate_id"]
        stream = client.get(f"/debate/{debate_id}/stream", headers=_auth_header(token))
        assert stream.status_code == 200


# ---------------------------------------------------------------------------
# Persistence (mocked)
# ---------------------------------------------------------------------------


class TestPersistence:

    @patch("app.main.save_debate", new_callable=AsyncMock)
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_save_debate_called_with_user_id(self, _jwt_secret, mock_save):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-persist-1")

        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "Persist test",
                "options": ["X", "Y"],
                "constraints": {"team_size": 2, "timeline": "3 months"},
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        mock_save.assert_called_once()
        assert mock_save.call_args[1]["user_id"] == "user-persist-1"
        assert mock_save.call_args[1]["preset_id"] == "developer"

    @patch("app.main.save_debate", new_callable=AsyncMock)
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_save_debate_called_with_user_id_on_authed_request(self, _jwt_secret, mock_save):
        SESSIONS.clear()
        client = TestClient(app)
        token = _make_token(sub="user-persist-anon")

        client.post(
            "/debate",
            json={
                "preset_id": "education",
                "question": "Authed persist",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_auth_header(token),
        )
        mock_save.assert_called_once()
        assert mock_save.call_args[1]["user_id"] == "user-persist-anon"


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


class TestAccessControl:

    @patch("app.main.list_debates_for_user", new_callable=AsyncMock)
    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_list_mine_delegates_to_storage(self, _jwt_secret, mock_list):
        mock_list.return_value = [
            {"id": "debate_abc", "preset_id": "developer", "question": "Q", "status": "complete", "created_at": "2026-01-01"}
        ]
        client = TestClient(app)
        token = _make_token(sub="user-list-1")

        resp = client.get("/debates/mine", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "debate_abc"
        mock_list.assert_called_once_with("user-list-1")

    @patch("app.auth._get_jwt_secret", return_value=_TEST_JWT_SECRET)
    def test_list_mine_returns_401_without_token(self, _jwt_secret):
        client = TestClient(app)
        resp = client.get("/debates/mine")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Contract shape: user_id in models
# ---------------------------------------------------------------------------


class TestContractV21:

    def test_debate_result_includes_optional_user_id(self):
        from app.contracts import DebateResult, ConsensusResult

        result = DebateResult(
            debate_id="debate_test", preset_id="developer", question="Q",
            options=["A", "B"], status="complete", agent_stances=[],
            cross_exam_transcript=[],
            consensus=ConsensusResult(
                winning_option="A", confidence_pct=80.0, agreement_pct=70.0,
                disagreement_pct=30.0, risks=[], option_breakdown=[], rationale="r",
            ),
            user_id="user-123",
        )
        assert result.user_id == "user-123"

    def test_debate_result_defaults_user_id_to_none(self):
        from app.contracts import DebateResult, ConsensusResult

        result = DebateResult(
            debate_id="debate_test2", preset_id="developer", question="Q",
            options=["A", "B"], status="complete", agent_stances=[],
            cross_exam_transcript=[],
            consensus=ConsensusResult(
                winning_option="A", confidence_pct=80.0, agreement_pct=70.0,
                disagreement_pct=30.0, risks=[], option_breakdown=[], rationale="r",
            ),
        )
        assert result.user_id is None

    def test_debate_state_includes_optional_user_id(self):
        from app.contracts import DebateState, Constraints

        state = DebateState(
            debate_id="debate_test3", preset_id="developer", question="Q",
            options=["A", "B"], constraints=Constraints(team_size=1, timeline="1 month"),
            user_id="user-456",
        )
        assert state.user_id == "user-456"

    def test_contract_version_is_21(self):
        from app.contracts import CONTRACT_VERSION
        assert CONTRACT_VERSION == "2.1"
