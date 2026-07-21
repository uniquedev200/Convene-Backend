from unittest.mock import patch

from fastapi.testclient import TestClient

from app.contracts import DOMAIN_REGISTRY, run_debate as _stub_run_debate
from app.main import SESSIONS, _resolve_run_debate, app

# Valid test JWT (matches default JWT_SECRET empty string in tests)
import time, jwt as pyjwt
_TEST_SECRET = "test-secret-api"
_TOKEN = pyjwt.encode(
    {"sub": "test-user-1", "exp": int(time.time()) + 3600, "iat": int(time.time())},
    _TEST_SECRET, algorithm="HS256",
)
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _patched_auth():
    return patch("app.auth._get_jwt_secret", return_value=_TEST_SECRET)


def test_presets_endpoint_returns_all_contract_presets():
    client = TestClient(app)

    response = client.get("/presets")

    assert response.status_code == 200
    preset_ids = {preset["preset_id"] for preset in response.json()}
    assert preset_ids == {"developer", "education", "startup"}


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.1"
    assert data["presets"] == len(DOMAIN_REGISTRY)
    assert data["tools"] == 4
    assert data["graph"] in ("stub", "loaded")
    assert data["agents"] in ("stub", "loaded")


@patch("app.main._resolve_run_debate", return_value=(_stub_run_debate, False))
@patch("app.auth._get_jwt_secret", return_value=_TEST_SECRET)
def test_create_debate_returns_id_and_result_matches_contract_stub(_jwt_mock, _mock_resolve):
    SESSIONS.clear()
    client = TestClient(app)

    response = client.post(
        "/debate",
        json={
            "preset_id": "startup",
            "question": "Should we use subscription or one-time pricing?",
            "options": ["Subscription", "One-time"],
            "constraints": {"team_size": 3, "timeline": "6 months", "budget": "low"},
        },
        headers=_AUTH,
    )

    assert response.status_code == 200
    data = response.json()
    debate_id = data["debate_id"]
    assert debate_id.startswith("debate_")
    assert "stream_url" in data
    assert "result_url" in data
    assert debate_id in data["stream_url"]
    assert debate_id in data["result_url"]
    result = client.get(f"/debate/{debate_id}/result", headers=_AUTH)
    assert result.status_code == 200
    assert result.json()["debate_id"] == debate_id
    assert result.json()["preset_id"] == "startup"


@patch("app.main._resolve_run_debate", return_value=(_stub_run_debate, False))
@patch("app.auth._get_jwt_secret", return_value=_TEST_SECRET)
def test_stream_uses_frozen_event_names(_jwt_mock, _mock_resolve):
    SESSIONS.clear()
    client = TestClient(app)
    created = client.post(
        "/debate",
        json={
            "preset_id": "developer",
            "question": "Postgres vs MongoDB?",
            "options": ["Postgres", "MongoDB"],
            "constraints": {"team_size": 3, "timeline": "6 months"},
        },
        headers=_AUTH,
    ).json()

    stream = client.get(f"/debate/{created['debate_id']}/stream", headers=_AUTH)

    assert stream.status_code == 200
    body = stream.text
    assert "event: agent_stance" in body
    assert "event: cross_exam" in body
    assert "event: consensus_final" in body
    # Verify SSE event IDs are present
    assert "id: " in body


def test_graph_live_events_are_pushed_before_result_stream_flattening():
    SESSIONS.clear()
    client = TestClient(app)

    with _patched_auth():
        created = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "Postgres vs MongoDB?",
                "options": ["Postgres", "MongoDB"],
                "constraints": {"team_size": 3, "timeline": "6 months"},
            },
            headers=_AUTH,
        ).json()
    debate_id = created["debate_id"]

    session = SESSIONS[debate_id]
    assert session.result is not None
    assert session.live_events
    live_body = "".join(session.live_events)
    assert "event: agent_stance" in live_body
    assert "event: tool_call" in live_body
    assert "event: cross_exam" in live_body


def test_real_graph_supports_live_event_sink_without_changing_run_debate_contract():
    _, supports_live = _resolve_run_debate()

    assert supports_live is True


@patch("app.main._resolve_run_debate", return_value=(_stub_run_debate, False))
@patch("app.auth._get_jwt_secret", return_value=_TEST_SECRET)
def test_all_presets_end_to_end(_jwt_mock, _mock_resolve):
    """Run a full debate through each preset and verify the contract shape."""
    SESSIONS.clear()
    client = TestClient(app)

    cases = [
        {
            "preset_id": "developer",
            "question": "Postgres vs MongoDB for a 3-person team, 6-month MVP",
            "options": ["Postgres", "MongoDB"],
            "constraints": {"team_size": 3, "timeline": "6 months"},
        },
        {
            "preset_id": "education",
            "question": "Should a student learn Rust or Go?",
            "options": ["Rust", "Go"],
            "constraints": {"team_size": 1, "timeline": "3 months"},
        },
        {
            "preset_id": "startup",
            "question": "Should our startup choose subscription or one-time pricing?",
            "options": ["Subscription", "One-time pricing"],
            "constraints": {"team_size": 4, "timeline": "6 months", "budget": "lean"},
        },
    ]

    for case in cases:
        created = client.post("/debate", json=case, headers=_AUTH).json()
        debate_id = created["debate_id"]

        result = client.get(f"/debate/{debate_id}/result", headers=_AUTH).json()
        assert result["debate_id"] == debate_id
        assert result["preset_id"] == case["preset_id"]
        assert result["status"] == "complete"
        assert result["consensus"]["winning_option"] in case["options"]
        assert len(result["agent_stances"]) == len(
            DOMAIN_REGISTRY[case["preset_id"]].personas
        ) * len(case["options"])


def test_github_repo_stats_inaccessible_for_education_and_startup():
    """Education and Startup agents must never reach github_repo_stats."""
    from app.tools_mcp import ToolAccessError, call_enabled_tool

    for preset_id in ("education", "startup"):
        try:
            call_enabled_tool(preset_id, "github_repo_stats", repo="facebook/react")
            assert False, f"ToolAccessError expected for preset {preset_id}"
        except ToolAccessError:
            pass


def test_unknown_debate_id_returns_404():
    client = TestClient(app)
    resp = client.get("/debate/nonexistent_debate_123/result")
    assert resp.status_code == 404


def test_invalid_preset_id_rejected():
    client = TestClient(app)
    with _patched_auth():
        resp = client.post(
            "/debate",
            json={
                "preset_id": "invalid_preset",
                "question": "test",
                "options": ["A", "B"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_AUTH,
        )
    assert resp.status_code == 422


def test_debate_request_requires_two_options():
    client = TestClient(app)
    with _patched_auth():
        resp = client.post(
            "/debate",
            json={
                "preset_id": "developer",
                "question": "test",
                "options": ["only_one"],
                "constraints": {"team_size": 1, "timeline": "1 month"},
            },
            headers=_AUTH,
        )
    assert resp.status_code == 422


def test_tools_endpoint_returns_all_tools_with_presets():
    client = TestClient(app)
    resp = client.get("/tools")
    assert resp.status_code == 200
    tools = resp.json()
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"web_search", "url_fetch", "document_reader", "github_repo_stats"}
    for tool in tools:
        assert "description" in tool
        assert "arguments" in tool
        assert "presets" in tool
        assert len(tool["presets"]) > 0

    web_search = next(t for t in tools if t["name"] == "web_search")
    assert set(web_search["presets"]) == {"developer", "education", "startup"}

    github = next(t for t in tools if t["name"] == "github_repo_stats")
    assert github["presets"] == ["developer"]
