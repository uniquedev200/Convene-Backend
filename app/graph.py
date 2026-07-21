"""Domain-agnostic DebateStack orchestration.

This module owns only the LangGraph lifecycle. Persona reasoning, tool use,
and score aggregation are injected through the frozen contract interfaces.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import logging

try:  # The dependency is intentionally imported lazily by the build setup.
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - exercised only in incomplete setups.
    END = START = None
    StateGraph = None

try:
    from .contracts import (
        AgentStance,
        ConsensusResult,
        Constraints,
        CrossExamMessage,
        DebateResult,
        DebateState,
        PresetId,
    )
except ImportError:  # Allows running graph.py with a flat module layout.
    from contracts import (  # type: ignore[no-redef]
        AgentStance,
        ConsensusResult,
        Constraints,
        CrossExamMessage,
        DebateResult,
        DebateState,
        PresetId,
    )


logger = logging.getLogger(__name__)
_event_sink: ContextVar[Callable[[str, object], None] | None] = ContextVar(
    "debatestack_event_sink",
    default=None,
)


class OrchestrationError(RuntimeError):
    """Raised when a debate cannot complete its orchestration lifecycle."""


@contextmanager
def event_sink(sink: Callable[[str, object], None]) -> Iterator[None]:
    """Install a per-request event sink without changing run_debate's contract."""

    token = _event_sink.set(sink)
    try:
        yield
    finally:
        _event_sink.reset(token)


def _require_langgraph() -> None:
    if StateGraph is None or START is None or END is None:
        raise OrchestrationError(
            "LangGraph is required to run DebateStack. Install the project's "
            "requirements before starting the API."
        )


def _get_preset(preset_id: PresetId):
    """Resolve a preset exclusively through the shared domain registry."""

    try:
        from .registry import DOMAIN_REGISTRY
    except ImportError:
        from registry import DOMAIN_REGISTRY  # type: ignore[no-redef]
    try:
        return DOMAIN_REGISTRY[preset_id]
    except KeyError as exc:
        raise OrchestrationError(f"Unknown preset_id: {preset_id!r}") from exc


def _run_persona(
    persona: object,
    question: str,
    options: list[str],
    constraints: Constraints,
) -> list[AgentStance]:
    """Invoke the contract-owned analysis function for one dynamic persona."""

    try:
        from .agents import run_agent_analysis
    except ImportError:
        from agents import run_agent_analysis  # type: ignore[no-redef]
    return run_agent_analysis(persona, question, options, constraints)  # type: ignore[arg-type]


def _stream_event(event: str, data: object) -> None:
    """Publish an optional LangGraph custom event for Person D's SSE adapter."""

    sink = _event_sink.get()
    if sink is not None:
        sink(event, data)

    try:
        from langgraph.config import get_stream_writer
    except ImportError:
        return
    try:
        get_stream_writer()({"event": event, "data": data})
    except RuntimeError:
        # Direct node tests may run outside a LangGraph streaming context.
        return


def initial_analysis(state: DebateState) -> dict[str, object]:
    """Run one analysis for every persona in the active preset.

    Personas execute concurrently because they are independent. Results are
    flattened in registry order to keep output and SSE event ordering stable.
    """

    preset = _get_preset(state.preset_id)
    personas = list(preset.personas)
    logger.info("Starting initial analysis: debate_id=%s personas=%d", state.debate_id, len(personas))

    try:
        with ThreadPoolExecutor(max_workers=max(1, len(personas))) as executor:
            futures = [
                executor.submit(
                    _run_persona,
                    persona,
                    state.question,
                    list(state.options),
                    state.constraints,
                )
                for persona in personas
            ]
            future_indexes = {future: index for index, future in enumerate(futures)}
            completed: list[tuple[int, list[AgentStance]]] = []
            tool_call_log = []
            for future in as_completed(futures):
                result = future.result()
                completed.append((future_indexes[future], result))
                for stance in result:
                    _stream_event("agent_stance", stance)
                    for tool_call in stance.tool_calls_used:
                        tool_call_log.append(tool_call)
                        _stream_event("tool_call", tool_call)
            completed.sort(key=lambda item: item[0])
            stances = [stance for _, result in completed for stance in result]
    except Exception as exc:
        logger.exception("Initial analysis failed: debate_id=%s", state.debate_id)
        raise OrchestrationError("Initial analysis failed") from exc

    return {
        "status": "analyzing",
        "agent_stances": stances,
        "tool_call_log": tool_call_log,
    }


def cross_examination(
    state: DebateState,
) -> dict[str, object]:
    """Coordinate the bounded cross-examination owned by Person B's agents module."""

    logger.info("Starting cross examination: debate_id=%s", state.debate_id)
    try:
        try:
            from .agents import run_cross_examination
        except ImportError:
            from agents import run_cross_examination  # type: ignore[no-redef]
        transcript: list[CrossExamMessage] = run_cross_examination(state)
    except Exception as exc:
        logger.exception("Cross examination failed: debate_id=%s", state.debate_id)
        raise OrchestrationError(
            "Cross examination failed; Person B's agents module must expose "
            "the agreed run_cross_examination implementation"
        ) from exc
    for message in transcript:
        _stream_event("cross_exam", message)
    return {"status": "cross_examining", "cross_exam_transcript": transcript}


def moderator_consensus(state: DebateState) -> dict[str, object]:
    """Delegate deterministic consensus calculation to the contract owner."""

    preset = _get_preset(state.preset_id)
    logger.info("Calculating consensus: debate_id=%s", state.debate_id)
    try:
        try:
            from .scoring import aggregate_scores
        except ImportError:
            from scoring import aggregate_scores  # type: ignore[no-redef]
        consensus: ConsensusResult = aggregate_scores(
            state.agent_stances,
            list(state.options),
            preset.scoring_weights,
        )
    except Exception as exc:
        logger.exception("Consensus calculation failed: debate_id=%s", state.debate_id)
        raise OrchestrationError("Consensus calculation failed") from exc
    return {"status": "complete", "consensus": consensus}


def build_debate_graph() -> object:
    """Build and compile the generic DebateStack StateGraph.

    The graph has no preset branches and no domain-specific knowledge. The
    Cross-examination is resolved from Person B's real agents module at node
    execution time; no business logic or fallback stub lives here.
    """

    _require_langgraph()
    graph = StateGraph(DebateState)
    graph.add_node("initial_analysis", initial_analysis)
    graph.add_node("cross_examination", cross_examination)
    graph.add_node("moderator_consensus", moderator_consensus)
    graph.add_edge(START, "initial_analysis")
    graph.add_edge("initial_analysis", "cross_examination")
    graph.add_edge("cross_examination", "moderator_consensus")
    graph.add_edge("moderator_consensus", END)
    return graph.compile()


@lru_cache(maxsize=1)
def _compiled_default_graph() -> object:
    """Compile the default graph once and reuse it for all API requests."""

    return build_debate_graph()


def _state_from_output(output: DebateState | dict[str, object]) -> DebateState:
    """Normalize LangGraph's output to the frozen Pydantic state model."""

    if isinstance(output, DebateState):
        return output
    return DebateState.model_validate(output)


def run_debate(
    debate_id: str,
    preset_id: PresetId,
    question: str,
    options: list[str],
    constraints: Constraints,
) -> DebateResult:
    """Run one complete debate and return the contract-defined result.

    Person D should call this function. The signature intentionally matches
    the frozen contract exactly.
    """

    _get_preset(preset_id)
    initial_state = DebateState(
        debate_id=debate_id,
        preset_id=preset_id,
        question=question,
        options=list(options),
        constraints=constraints,
    )
    logger.info("Running debate: debate_id=%s preset_id=%s", debate_id, preset_id)
    try:
        compiled = _compiled_default_graph()
        final_state = _state_from_output(compiled.invoke(initial_state))  # type: ignore[attr-defined]
    except OrchestrationError:
        raise
    except Exception as exc:
        logger.exception("Debate failed: debate_id=%s", debate_id)
        raise OrchestrationError(f"Debate failed: {debate_id}") from exc

    if final_state.consensus is None:
        raise OrchestrationError("Graph completed without a consensus result")
    return DebateResult(
        debate_id=final_state.debate_id,
        preset_id=final_state.preset_id,
        question=final_state.question,
        options=final_state.options,
        status=final_state.status,
        agent_stances=final_state.agent_stances,
        cross_exam_transcript=final_state.cross_exam_transcript,
        consensus=final_state.consensus,
    )


__all__ = [
    "OrchestrationError",
    "build_debate_graph",
    "cross_examination",
    "event_sink",
    "initial_analysis",
    "moderator_consensus",
    "run_debate",
]
