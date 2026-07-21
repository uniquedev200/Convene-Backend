"""FastAPI API/infra layer for DebateStack.

Person D owns this module. It calls only run_debate() from orchestration,
stores sessions by debate_id, and exposes the frozen API/SSE contract.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from importlib import import_module
from typing import Annotated, Callable, Any

logger = logging.getLogger(__name__)

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is optional at runtime.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from .contracts import (
    DOMAIN_REGISTRY,
    DebateRequest,
    DebateResult,
    DebateStatus,
    MCP_TOOL_DEFINITIONS,
    PresetConfig,
    new_debate_id,
    run_debate as contract_run_debate,
)
from .streaming import (
    agent_stance_event,
    cross_exam_event,
    error_event,
    result_to_sse_events,
    tool_call_event,
)
from .tools_mcp import get_enabled_tool_names
from .auth import _decode_token, get_current_user, router as auth_router
from .storage import (
    save_debate,
    update_debate_result,
    update_debate_status,
    list_debates_for_user,
    get_debate_owner,
    get_debate_from_db,
)


RunDebate = Callable[..., DebateResult]


APP_VERSION = "2.1"


class DebateCreated(BaseModel):
    debate_id: str
    stream_url: str
    result_url: str


class HealthResponse(BaseModel):
    status: str
    version: str
    presets: int
    tools: int
    graph: str
    agents: str


@dataclass
class DebateSession:
    debate_id: str
    preset_id: str
    user_id: str | None = None
    status: DebateStatus = "pending"
    created_at: float = 0.0
    result: DebateResult | None = None
    error_message: str | None = None
    live_events: list[str] = field(default_factory=list)
    _event_ready: asyncio.Event = field(default_factory=asyncio.Event)

    def push_event(self, sse_text: str) -> None:
        """Called by graph nodes to push a real-time SSE event."""
        self.live_events.append(sse_text)
        self._event_ready.set()


SESSIONS: dict[str, DebateSession] = {}
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour
MAX_CONCURRENT_DEBATES: int = int(os.getenv("MAX_CONCURRENT_DEBATES", "10"))
_main_loop: asyncio.AbstractEventLoop | None = None


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _rate_limit_per_minute() -> int:
    return int(os.getenv("DEBATE_RATE_LIMIT_PER_MINUTE", "10"))


def _cleanup_expired_sessions() -> None:
    """Remove sessions older than SESSION_TTL_SECONDS and completed/failed ones."""
    now = time.time()
    expired = [
        did
        for did, s in SESSIONS.items()
        if (now - s.created_at > SESSION_TTL_SECONDS)
        or s.status in ("complete", "failed")
    ]
    for did in expired:
        SESSIONS.pop(did, None)
    if expired:
        logger.debug("Cleaned up %d expired sessions", len(expired))


def _count_in_flight() -> int:
    """Count debates currently running (not complete/failed)."""
    return sum(
        1 for s in SESSIONS.values() if s.status not in ("complete", "failed")
    )


def _check_rate_limit(user_id: str) -> None:
    limit = _rate_limit_per_minute()
    if limit <= 0:
        return
    now = time.time()
    window_start = now - 60
    bucket = [t for t in RATE_LIMIT_BUCKETS.get(user_id, []) if t >= window_start]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)
    RATE_LIMIT_BUCKETS[user_id] = bucket


def _resolve_run_debate() -> tuple[RunDebate, bool]:
    """Return (run_debate_fn, supports_live_events).

    Person A's frozen public contract is ``run_debate(...)`` with no
    callback parameter. Live SSE can be added later via a separate adapter,
    but the API must not mutate the shared interface.
    """
    try:
        graph = import_module("app.graph")
        # StateGraph is None when langgraph isn't installed — fall back to stub.
        if getattr(graph, "StateGraph", None) is None:
            return contract_run_debate, False
        fn = getattr(graph, "run_debate")
        return fn, hasattr(graph, "event_sink")
    except (ImportError, AttributeError):
        return contract_run_debate, False


def _encode_live_event(event: str, data: object, event_id: str) -> str | None:
    if event == "agent_stance":
        return agent_stance_event(data, event_id)
    if event == "tool_call":
        return tool_call_event(data, event_id)
    if event == "cross_exam":
        return cross_exam_event(data, event_id)
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="DebateStack API", version="2.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)

    @app.on_event("startup")
    async def _capture_main_loop():
        global _main_loop
        _main_loop = asyncio.get_running_loop()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        graph_status = "stub"
        try:
            import_module("app.graph")
            graph_status = "loaded"
        except (ImportError, AttributeError, OSError):
            pass
        agents_status = "stub"
        try:
            import_module("app.agents")
            agents_status = "loaded"
        except (ImportError, AttributeError, OSError):
            pass
        return HealthResponse(
            status="ok",
            version=APP_VERSION,
            presets=len(DOMAIN_REGISTRY),
            tools=len(MCP_TOOL_DEFINITIONS),
            graph=graph_status,
            agents=agents_status,
        )

    @app.get("/presets", response_model=list[PresetConfig])
    def list_presets() -> list[PresetConfig]:
        return list(DOMAIN_REGISTRY.values())

    @app.get("/tools")
    def list_tools() -> list[dict]:
        from .contracts import MCP_TOOL_DEFINITIONS

        all_tools = {}
        for defn in MCP_TOOL_DEFINITIONS:
            all_tools[defn["name"]] = {
                "name": defn["name"],
                "description": defn["description"],
                "arguments": defn["input_schema"].get("properties", {}),
                "presets": [],
            }
        for preset_id in DOMAIN_REGISTRY:
            for tool_name in get_enabled_tool_names(preset_id):
                if tool_name in all_tools:
                    all_tools[tool_name]["presets"].append(preset_id)
        return list(all_tools.values())

    @app.post("/debate", response_model=DebateCreated)
    async def create_debate(
        debate: DebateRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        user_id: Annotated[str, Depends(get_current_user)],
    ) -> DebateCreated:
        if user_id is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        _cleanup_expired_sessions()

        if _count_in_flight() >= MAX_CONCURRENT_DEBATES:
            raise HTTPException(
                status_code=503,
                detail="Server is at capacity. Try again shortly.",
            )

        _check_rate_limit(user_id)

        debate_id = new_debate_id()
        SESSIONS[debate_id] = DebateSession(
            debate_id=debate_id,
            preset_id=debate.preset_id,
            user_id=user_id,
            status="pending",
            created_at=time.time(),
        )

        # Persist to database (fire-and-forget, never blocks)
        background_tasks.add_task(_persist_debate, debate_id, user_id, debate)

        background_tasks.add_task(_run_debate_job, debate_id, debate)
        base = str(request.base_url).rstrip("/")
        return DebateCreated(
            debate_id=debate_id,
            stream_url=f"{base}/debate/{debate_id}/stream",
            result_url=f"{base}/debate/{debate_id}/result",
        )

    @app.get("/debates/mine")
    async def list_my_debates(
        user_id: Annotated[str | None, Depends(get_current_user)],
    ) -> list[dict]:
        if user_id is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return await list_debates_for_user(user_id)

    @app.get("/debate/{debate_id}/result", response_model=DebateResult)
    async def get_result(
        debate_id: str,
        user_id: Annotated[str | None, Depends(get_current_user)],
    ) -> DebateResult:
        session = SESSIONS.get(debate_id)
        if session is not None:
            _check_debate_access(session, user_id)
            if session.status == "failed":
                raise HTTPException(status_code=502, detail=session.error_message or "Debate failed")
            if session.result is None:
                raise HTTPException(status_code=202, detail={"status": session.status})
            return session.result

        db_row = await get_debate_from_db(debate_id)
        if db_row is None:
            raise HTTPException(status_code=404, detail="Unknown debate_id")

        if user_id is not None and db_row.get("user_id") and db_row["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if db_row["status"] == "failed":
            raise HTTPException(status_code=502, detail="Debate failed")
        if db_row["status"] != "complete" or db_row.get("result") is None:
            raise HTTPException(status_code=202, detail={"status": db_row["status"]})

        from app.contracts import DebateResult as DR
        return DR.model_validate(db_row["result"])

    @app.get("/debate/{debate_id}/stream")
    async def stream_result(
        debate_id: str,
        token: str | None = None,
        user_id: Annotated[str | None, Depends(get_current_user)] = None,
    ) -> StreamingResponse:
        if user_id is None and token:
            try:
                payload = _decode_token(token)
                user_id = payload.get("sub")
            except Exception:
                pass
        session = _get_session(debate_id)
        _check_debate_access(session, user_id)
        return StreamingResponse(
            _stream_session(debate_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def _get_session(debate_id: str) -> DebateSession:
    session = SESSIONS.get(debate_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown debate_id")
    return session


def _check_debate_access(session: DebateSession, user_id: str | None) -> None:
    """Deny access if debate is owned by someone else."""
    if session.user_id is not None and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")


async def _persist_debate(
    debate_id: str,
    user_id: str | None,
    debate: DebateRequest,
) -> None:
    """Fire-and-forget: save new debate to database."""
    await save_debate(
        debate_id=debate_id,
        user_id=user_id,
        preset_id=debate.preset_id,
        question=debate.question,
        options=debate.options,
    )


async def _persist_debate_result(debate_id: str, result: DebateResult) -> None:
    """Fire-and-forget: save completed debate result to database. Retries once on failure."""
    for attempt in range(3):
        try:
            await update_debate_result(debate_id, result.model_dump(mode="json"))
            return
        except Exception:
            if attempt < 2:
                await asyncio.sleep(1 * (attempt + 1))
            else:
                logger.error("Failed to persist result for %s after %d attempts", debate_id, attempt + 1)


def _run_debate_job(debate_id: str, debate: DebateRequest) -> None:
    session = SESSIONS[debate_id]
    session.status = "analyzing"
    try:
        run_debate_fn, supports_live = _resolve_run_debate()
        event_counter = 0

        def _on_event(event: str, data: object) -> None:
            nonlocal event_counter
            event_counter += 1
            sse_text = _encode_live_event(event, data, str(event_counter))
            if sse_text is not None:
                session.push_event(sse_text)

        if supports_live:
            graph = import_module("app.graph")
            with graph.event_sink(_on_event):
                result = run_debate_fn(
                    debate_id=debate_id,
                    preset_id=debate.preset_id,
                    question=debate.question,
                    options=debate.options,
                    constraints=debate.constraints,
                )
        else:
            result = run_debate_fn(
                debate_id=debate_id,
                preset_id=debate.preset_id,
                question=debate.question,
                options=debate.options,
                constraints=debate.constraints,
            )

        session.result = result
        session.status = result.status
        # Persist completed result to database (fire-and-forget, never crashes debate)
        # _run_debate_job runs in a thread executor (FastAPI BackgroundTasks),
        # so we schedule the async persist back onto the main event loop that
        # owns the asyncpg pool.
        loop = _main_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _persist_debate_result(debate_id, result), loop
            )
        else:
            logger.warning(
                "No running event loop — skipping result persistence for %s",
                debate_id,
            )
    except Exception as exc:
        session.status = "failed"
        session.error_message = str(exc)
        loop = _main_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                update_debate_status(debate_id, "failed"), loop
            )
    finally:
        session._event_ready.set()


async def _stream_session(debate_id: str):
    event_idx = 0
    last_keepalive = 0.0
    while True:
        session = SESSIONS[debate_id]

        # Yield any live events that arrived since last check
        while event_idx < len(session.live_events):
            yield session.live_events[event_idx]
            event_idx += 1

        if session.result is not None:
            # Drain any remaining live events
            while event_idx < len(session.live_events):
                yield session.live_events[event_idx]
                event_idx += 1
            # If graph pushed live events, only emit consensus_final from result
            had_live = len(session.live_events) > 0
            for event in result_to_sse_events(
                session.result,
                live_events_already_streamed=had_live,
                start_event_id=event_idx,
            ):
                yield event
            return

        if session.status == "failed":
            yield error_event(session.error_message or "Debate failed", recoverable=False)
            return

        now = time.time()
        if now - last_keepalive >= 10:
            yield ": keep-alive\n\n"
            last_keepalive = now
        await asyncio.sleep(0.25)


app = create_app()
