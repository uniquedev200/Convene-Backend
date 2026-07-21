"""SSE serialization helpers for DebateStack API routes."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from .contracts import (
    ConsensusResult,
    DebateResult,
    SSEAgentStanceEvent,
    SSEConsensusEvent,
    SSECrossExamEvent,
    SSEErrorEvent,
    SSEToolCallEvent,
)


def _jsonable(data: Any) -> str:
    if isinstance(data, BaseModel):
        if hasattr(data, "model_dump_json"):
            return data.model_dump_json()
        return data.json()
    return json.dumps(data)


def encode_sse(event: str, data: Any, event_id: str | None = None) -> str:
    id_line = f"id: {event_id}\n" if event_id else ""
    return f"{id_line}event: {event}\ndata: {_jsonable(data)}\n\n"


def agent_stance_event(data: Any, event_id: str | None = None) -> str:
    return encode_sse(SSEAgentStanceEvent(data=data).event, data, event_id)


def tool_call_event(data: Any, event_id: str | None = None) -> str:
    return encode_sse(SSEToolCallEvent(data=data).event, data, event_id)


def cross_exam_event(data: Any, event_id: str | None = None) -> str:
    return encode_sse(SSECrossExamEvent(data=data).event, data, event_id)


def consensus_event(data: ConsensusResult, event_id: str | None = None) -> str:
    return encode_sse(SSEConsensusEvent(data=data).event, data, event_id)


def error_event(message: str, *, recoverable: bool = False, event_id: str | None = None) -> str:
    payload = {"message": message, "recoverable": recoverable}
    return encode_sse(SSEErrorEvent(data=payload).event, payload, event_id)


def result_to_sse_events(
    result: DebateResult,
    *,
    live_events_already_streamed: bool = False,
    start_event_id: int = 0,
) -> Iterable[str]:
    """Flatten a completed DebateResult into the frozen SSE event stream.

    When ``live_events_already_streamed`` is True the graph already pushed
    stance / tool_call / cross_exam events in real-time, so we only need
    to emit the terminal consensus_final event.
    """
    eid = start_event_id
    if not live_events_already_streamed:
        for stance in result.agent_stances:
            eid += 1
            yield agent_stance_event(stance, str(eid))
            for tool_call in stance.tool_calls_used:
                eid += 1
                yield tool_call_event(tool_call, str(eid))
        for message in result.cross_exam_transcript:
            eid += 1
            yield cross_exam_event(message, str(eid))
    eid += 1
    yield consensus_event(result.consensus, str(eid))

