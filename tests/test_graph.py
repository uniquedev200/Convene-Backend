"""Unit tests for DebateStack's orchestration layer."""

from __future__ import annotations

from types import ModuleType
import sys
from typing import Any

import pytest

pytest.importorskip("langgraph")

from app import contracts
from app import graph


def _preset(
    personas: list[contracts.PersonaConfig],
    preset_id: contracts.PresetId = "developer",
) -> contracts.PresetConfig:
    return contracts.PresetConfig(
        preset_id=preset_id,
        display_name=f"Test {preset_id.title()}",
        personas=personas,
        enabled_tools=["web_search"],
        scoring_weights={},
        starter_prompts=[],
    )


def _persona(name: str) -> contracts.PersonaConfig:
    return contracts.PersonaConfig(
        agent_name=name,
        evaluation_dimension="test dimension",
        system_prompt="test prompt",
    )


def _state(preset_id: contracts.PresetId = "developer") -> contracts.DebateState:
    return contracts.DebateState(
        debate_id="debate_test",
        preset_id=preset_id,
        question="Which option should we choose?",
        options=["A", "B"],
        constraints=contracts.Constraints(team_size=3, timeline="2 days"),
    )


@pytest.fixture
def person_b_modules(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install isolated Person B doubles without changing production code."""

    personas = [_persona("Alpha"), _persona("Beta")]
    registry = ModuleType("app.registry")
    registry.DOMAIN_REGISTRY = {
        "developer": _preset(personas, "developer"),
        "education": _preset([_persona("Professor"), _persona("Recruiter")], "education"),
        "startup": _preset([_persona("Founder"), _persona("Investor")], "startup"),
    }

    agents = ModuleType("app.agents")
    agents.analysis_calls = []
    agents.cross_exam_calls = []
    agents.phase_log = []
    agents.raise_analysis = False
    agents.raise_cross_exam = False

    tools = ModuleType("app.tools_mcp")
    tools.raise_web_search = False

    def web_search(query: str) -> contracts.ToolResult:
        if tools.raise_web_search:
            raise RuntimeError("web_search failure")
        return contracts.ToolResult(
            tool_name="web_search",
            query=query,
            result_summary="test result",
        )

    tools.web_search = web_search

    def run_agent_analysis(
        persona: contracts.PersonaConfig,
        question: str,
        options: list[str],
        constraints: contracts.Constraints,
    ) -> list[contracts.AgentStance]:
        agents.analysis_calls.append((persona.agent_name, question, options, constraints))
        agents.phase_log.append("initial_analysis")
        if agents.raise_analysis:
            raise RuntimeError("agent failure")
        return [
            contracts.AgentStance(
                agent_name=persona.agent_name,
                option=option,
                score=8.0,
                reasoning=f"{persona.agent_name} supports {option}",
                tool_calls_used=(
                    [
                        contracts.ToolCall.model_validate(
                            web_search(f"{persona.agent_name}:{option}").model_dump()
                        )
                    ]
                    if option == "A"
                    else []
                ),
            )
            for option in options
        ]

    def run_cross_examination(state: contracts.DebateState) -> list[contracts.CrossExamMessage]:
        agents.cross_exam_calls.append(state.debate_id)
        agents.phase_log.append("cross_examination")
        if agents.raise_cross_exam:
            raise RuntimeError("cross-examination failure")
        if not state.agent_stances:
            return []
        return [
            contracts.CrossExamMessage(
                from_agent=state.agent_stances[0].agent_name,
                to_agent=state.agent_stances[-1].agent_name,
                challenge="Why?",
                response="Because.",
            )
        ]

    agents.run_agent_analysis = run_agent_analysis
    agents.run_cross_examination = run_cross_examination

    scoring = ModuleType("app.scoring")
    scoring.raise_scoring = False

    def aggregate_scores(
        all_stances: list[contracts.AgentStance],
        options: list[str],
        scoring_weights: dict[str, float] | None = None,
    ) -> contracts.ConsensusResult:
        del all_stances, scoring_weights
        agents.phase_log.append("moderator_consensus")
        if scoring.raise_scoring:
            raise RuntimeError("scoring failure")
        return contracts.ConsensusResult(
            winning_option=options[0],
            confidence_pct=90.0,
            agreement_pct=80.0,
            disagreement_pct=20.0,
            risks=[],
            option_breakdown=[
                contracts.OptionResult(option=option, average_score=8.0)
                for option in options
            ],
            rationale="test consensus",
        )

    scoring.aggregate_scores = aggregate_scores

    monkeypatch.setitem(sys.modules, "app.registry", registry)
    monkeypatch.setitem(sys.modules, "app.agents", agents)
    monkeypatch.setitem(sys.modules, "app.scoring", scoring)
    monkeypatch.setitem(sys.modules, "app.tools_mcp", tools)
    graph._compiled_default_graph.cache_clear()
    yield {"registry": registry, "agents": agents, "scoring": scoring, "tools": tools}
    graph._compiled_default_graph.cache_clear()


def test_preset_loading_uses_registry_personas(
    person_b_modules: dict[str, Any],
) -> None:
    result = graph.initial_analysis(_state())

    assert [call[0] for call in person_b_modules["agents"].analysis_calls] == [
        "Alpha",
        "Beta",
    ]
    assert len(result["agent_stances"]) == 4


def test_graph_compiles_with_required_nodes_and_edges(
    person_b_modules: dict[str, Any],
) -> None:
    compiled = graph.build_debate_graph()
    graph_data = compiled.get_graph()

    assert {"initial_analysis", "cross_examination", "moderator_consensus"} <= set(
        graph_data.nodes
    )
    edges = {(edge.source, edge.target) for edge in graph_data.edges}
    assert ("__start__", "initial_analysis") in edges
    assert ("initial_analysis", "cross_examination") in edges
    assert ("cross_examination", "moderator_consensus") in edges
    assert ("moderator_consensus", "__end__") in edges


def test_state_transitions_complete_the_lifecycle(
    person_b_modules: dict[str, Any],
) -> None:
    initial = _state()
    after_analysis = graph.initial_analysis(initial)
    analyzing = initial.model_copy(update=after_analysis)
    after_cross_exam = graph.cross_examination(analyzing)
    cross_examining = analyzing.model_copy(update=after_cross_exam)
    after_consensus = graph.moderator_consensus(cross_examining)

    assert after_analysis["status"] == "analyzing"
    assert after_cross_exam["status"] == "cross_examining"
    assert after_consensus["status"] == "complete"
    assert after_consensus["consensus"].winning_option == "A"


def test_invalid_preset_id_is_rejected(
    person_b_modules: dict[str, Any],
) -> None:
    with pytest.raises(graph.OrchestrationError, match="Unknown preset_id"):
        graph.run_debate(
            "debate_invalid",
            "not-a-preset",  # type: ignore[arg-type]
            "Question",
            ["A", "B"],
            contracts.Constraints(team_size=1, timeline="1 day"),
        )


def test_empty_persona_list_is_valid_and_does_not_crash(
    person_b_modules: dict[str, Any],
) -> None:
    person_b_modules["registry"].DOMAIN_REGISTRY["developer"] = _preset([])

    result = graph.initial_analysis(_state())

    assert result["status"] == "analyzing"
    assert result["agent_stances"] == []
    assert result["tool_call_log"] == []


def test_run_debate_returns_contract_defined_result(
    person_b_modules: dict[str, Any],
) -> None:
    result = graph.run_debate(
        "debate_run",
        "developer",
        "Question",
        ["A", "B"],
        contracts.Constraints(team_size=2, timeline="2 days"),
    )

    assert isinstance(result, contracts.DebateResult)
    assert result.debate_id == "debate_run"
    assert result.preset_id == "developer"
    assert result.status == "complete"
    assert result.consensus.winning_option == "A"
    assert result.cross_exam_transcript[0].challenge == "Why?"


def test_agent_errors_are_wrapped_as_orchestration_errors(
    person_b_modules: dict[str, Any],
) -> None:
    person_b_modules["agents"].raise_analysis = True

    with pytest.raises(graph.OrchestrationError, match="Initial analysis failed"):
        graph.initial_analysis(_state())


def test_cross_examination_errors_are_wrapped(
    person_b_modules: dict[str, Any],
) -> None:
    person_b_modules["agents"].raise_cross_exam = True
    state = _state().model_copy(
        update={"agent_stances": [
            contracts.AgentStance(
                agent_name="Alpha",
                option="A",
                score=8,
                reasoning="test",
            )
        ]}
    )

    with pytest.raises(graph.OrchestrationError, match="Cross examination failed"):
        graph.cross_examination(state)


def test_scoring_errors_are_wrapped(
    person_b_modules: dict[str, Any],
) -> None:
    person_b_modules["scoring"].raise_scoring = True

    with pytest.raises(graph.OrchestrationError, match="Consensus calculation failed"):
        graph.moderator_consensus(_state())


def test_tool_call_log_is_populated_from_agent_stances(
    person_b_modules: dict[str, Any],
) -> None:
    result = graph.initial_analysis(_state())

    tool_call_log = result["tool_call_log"]
    assert len(tool_call_log) == 2
    assert all(call.tool_name == "web_search" for call in tool_call_log)
    assert {call.query for call in tool_call_log} == {"Alpha:A", "Beta:A"}


def test_default_compiled_graph_is_reused(
    person_b_modules: dict[str, Any],
) -> None:
    first = graph._compiled_default_graph()
    second = graph._compiled_default_graph()

    assert first is second


def test_same_graph_supports_all_registry_presets(
    person_b_modules: dict[str, Any],
) -> None:
    compiled = graph.build_debate_graph()
    expected_personas = {
        "developer": {"Alpha", "Beta"},
        "education": {"Professor", "Recruiter"},
        "startup": {"Founder", "Investor"},
    }

    for preset_id, expected in expected_personas.items():
        result = compiled.invoke(_state(preset_id))
        assert result["status"] == "complete"
        assert {stance.agent_name for stance in result["agent_stances"]} == expected

    assert len(person_b_modules["agents"].analysis_calls) == 6


def test_person_c_tool_failure_is_wrapped_and_state_is_unchanged(
    person_b_modules: dict[str, Any],
) -> None:
    person_b_modules["tools"].raise_web_search = True
    initial = _state()

    with pytest.raises(graph.OrchestrationError, match="Initial analysis failed"):
        graph.initial_analysis(initial)

    assert initial.status == "pending"
    assert initial.agent_stances == []
    assert initial.tool_call_log == []
    assert initial.cross_exam_transcript == []
    assert initial.consensus is None


def test_all_parallel_personas_finish_before_consensus(
    person_b_modules: dict[str, Any],
) -> None:
    result = graph.run_debate(
        "debate_parallel",
        "developer",
        "Question",
        ["A", "B"],
        contracts.Constraints(team_size=2, timeline="2 days"),
    )

    assert len(result.agent_stances) == 4
    assert {stance.agent_name for stance in result.agent_stances} == {"Alpha", "Beta"}
    assert person_b_modules["agents"].phase_log[-1] == "moderator_consensus"
    assert person_b_modules["agents"].phase_log.count("initial_analysis") == 2


def test_compiled_graph_is_reused_across_many_debates(
    person_b_modules: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_build = graph.build_debate_graph
    build_calls: list[object] = []

    def tracked_build() -> object:
        compiled = original_build()
        build_calls.append(compiled)
        return compiled

    monkeypatch.setattr(graph, "build_debate_graph", tracked_build)
    results = [
        graph.run_debate(
            f"debate_{index}",
            "developer",
            "Question",
            ["A", "B"],
            contracts.Constraints(team_size=2, timeline="2 days"),
        )
        for index in range(10)
    ]

    assert len(results) == 10
    assert all(result.status == "complete" for result in results)
    assert len(build_calls) == 1


def test_stream_events_and_lifecycle_are_ordered(
    person_b_modules: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streamed: list[tuple[str, object]] = []
    monkeypatch.setattr(
        graph,
        "_stream_event",
        lambda event, data: streamed.append((event, data)),
    )

    graph.run_debate(
        "debate_stream",
        "developer",
        "Question",
        ["A", "B"],
        contracts.Constraints(team_size=2, timeline="2 days"),
    )

    phase_log = person_b_modules["agents"].phase_log
    assert phase_log[:2] == ["initial_analysis", "initial_analysis"]
    assert phase_log[2:] == ["cross_examination", "moderator_consensus"]

    event_types = [event for event, _ in streamed]
    assert event_types
    assert all(event in {"agent_stance", "tool_call", "cross_exam"} for event in event_types)
    assert event_types.index("cross_exam") > event_types.index("agent_stance")
    assert max(
        index for index, event in enumerate(event_types) if event in {"agent_stance", "tool_call"}
    ) < event_types.index("cross_exam")
