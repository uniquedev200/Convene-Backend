"""
DebateStack — Shared Backend Contract
======================================
CONTRACT_VERSION = "2.1"

***********************************************************************
* MAJOR CHANGE IN v2.0 -- READ THIS BEFORE TOUCHING YOUR CODE          *
***********************************************************************
DebateStack is no longer three separate agent line-ups. It is ONE engine
(one LangGraph, one moderator, one scoring system) configured per request
by a PRESET pulled from the DOMAIN_REGISTRY below. Presets differ ONLY in:
agent personas, enabled tools, scoring weights, and starter prompts. The
graph structure, moderator logic, and scoring MATH are domain-agnostic
and must never branch on preset_id.

If you are hardcoding "Architect"/"Security"/etc. persona names or
prompts anywhere in your node/agent logic -- STOP. Pull them from
DOMAIN_REGISTRY[preset_id].personas instead. That's the entire point
of this version.

Commit this file FIRST, before anyone opens Codex on their own piece.
Nobody edits this file alone after a freeze -- any change is a 2-minute
heads-up to the other 3 people, then bump CONTRACT_VERSION, log it below,
re-share/re-commit so everyone pulls the same file before continuing.
This changelog IS the heads-up -- if it's not logged here, it didn't happen.

CHANGELOG:
  1.0 -- initial freeze: core models, function signatures, SSE events, API surface
  1.1 -- added DebateState (LangGraph working state), real MCP tool schemas,
         debate status lifecycle, debate_id generator, env config template
   2.0 -- MAJOR: introduced Domain Registry / preset system. One engine, three
          presets (developer/education/startup) via config, not three builds.
          Added PersonaConfig, PresetConfig, DOMAIN_REGISTRY, PresetId.
          DebateRequest and DebateState now require preset_id. Tools
          reorganized: generic tools (web_search, url_fetch, document_reader)
          available to every preset; github_repo_stats is Developer-only,
          gated by preset.enabled_tools. Added GET /presets endpoint.
          run_agent_analysis and run_debate signatures changed to take
          PersonaConfig / preset_id instead of raw agent_name strings.
   2.1 -- Added optional user_id field to DebateState and DebateResult for
          Supabase auth integration. Anonymous debates (user_id=None) remain
          fully functional. Backend verifies JWTs but never issues them.

Every stub function below returns hardcoded dummy data matching the
agreed shape. Build against these stubs. When your real piece is ready,
swap the stub for the real implementation -- the function signature
never changes, so nothing that depends on it breaks.
"""

from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field

CONTRACT_VERSION = "2.1"


# ---------------------------------------------------------------------------
# 0. DOMAIN REGISTRY -- the entire v2 strategy lives here.
#    Content owned by Person B. Structure (the field shapes) frozen by the
#    group. Adding a new domain later = adding one more PresetConfig entry.
#    Nothing in graph.py, agents.py, tools_mcp.py, or main.py should ever
#    need to change to support a new preset.
# ---------------------------------------------------------------------------

PresetId = Literal["developer", "education", "startup"]


class PersonaConfig(BaseModel):
    agent_name: str                 # e.g. "Architect", "Professor"
    evaluation_dimension: str       # what this agent scores options on
    system_prompt: str              # full persona system prompt, used as-is


class PresetConfig(BaseModel):
    preset_id: PresetId
    display_name: str
    personas: list[PersonaConfig]                  # domain experts (Moderator is global, not listed here)
    enabled_tools: list[str]                        # subset of tool names from MCP_TOOL_DEFINITIONS
    scoring_weights: dict[str, float] = Field(default_factory=dict)  # agent_name -> weight; empty = equal weight
    starter_prompts: list[str] = Field(default_factory=list)


DOMAIN_REGISTRY: dict[PresetId, PresetConfig] = {
    "developer": PresetConfig(
        preset_id="developer",
        display_name="Developer",
        personas=[
            PersonaConfig(
                agent_name="Architect",
                evaluation_dimension="Maintainability & complexity fit",
                system_prompt=(
                    "You are a senior software architect. Evaluate each option "
                    "for long-term maintainability and complexity fit given the "
                    "team size and timeline. Use your tools before forming an "
                    "opinion. Output a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Security",
                evaluation_dimension="Attack surface & data risk",
                system_prompt=(
                    "You are a security engineer. Evaluate each option for "
                    "attack surface and data-handling risk. Use your tools "
                    "before forming an opinion. Output a score 1-10 and "
                    "concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Performance",
                evaluation_dimension="Latency, scaling, ops burden",
                system_prompt=(
                    "You are a performance/DevOps engineer. Evaluate each "
                    "option for latency, scaling behavior, and operational "
                    "burden. Use your tools before forming an opinion. Output "
                    "a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="ProductDX",
                evaluation_dimension="Time-to-ship & developer experience",
                system_prompt=(
                    "You are a product-minded engineering lead. Evaluate each "
                    "option for time-to-ship and developer experience. Use "
                    "your tools before forming an opinion. Output a score "
                    "1-10 and concise reasoning."
                ),
            ),
        ],
        enabled_tools=["web_search", "github_repo_stats", "url_fetch"],
        starter_prompts=[
            "Postgres vs MongoDB for a 3-person team, 6-month MVP",
            "Monolith vs microservices for a 5-engineer startup",
        ],
    ),
    "education": PresetConfig(
        preset_id="education",
        display_name="Education",
        personas=[
            PersonaConfig(
                agent_name="Professor",
                evaluation_dimension="Learning depth & academic rigor",
                system_prompt=(
                    "You are a computer science professor. Evaluate each "
                    "option for how much genuine understanding the student "
                    "will build. Use your tools before forming an opinion. "
                    "Output a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="IndustryEngineer",
                evaluation_dimension="Real-world relevance",
                system_prompt=(
                    "You are a working software engineer. Evaluate each "
                    "option for how relevant it is to real industry work "
                    "today. Use your tools before forming an opinion. Output "
                    "a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Recruiter",
                evaluation_dimension="Career & hiring signal",
                system_prompt=(
                    "You are a technical recruiter. Evaluate each option for "
                    "how strong a signal it sends to employers. Use your "
                    "tools before forming an opinion. Output a score 1-10 "
                    "and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="ResearchScientist",
                evaluation_dimension="Theoretical depth",
                system_prompt=(
                    "You are a research scientist. Evaluate each option for "
                    "the depth of theoretical foundation it builds. Use your "
                    "tools before forming an opinion. Output a score 1-10 "
                    "and concise reasoning."
                ),
            ),
        ],
        enabled_tools=["web_search", "document_reader"],
        starter_prompts=[
            "Should a student learn Rust or Go?",
            "Which final-year project should I build: a compiler or a distributed database?",
        ],
    ),
    "startup": PresetConfig(
        preset_id="startup",
        display_name="Startup",
        personas=[
            PersonaConfig(
                agent_name="Investor",
                evaluation_dimension="ROI & market fit",
                system_prompt=(
                    "You are a venture investor. Evaluate each option for "
                    "ROI potential and market fit. Use your tools before "
                    "forming an opinion. Output a score 1-10 and concise "
                    "reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Founder",
                evaluation_dimension="Execution speed & founder bandwidth",
                system_prompt=(
                    "You are an experienced startup founder. Evaluate each "
                    "option for how fast a small team can realistically "
                    "execute it. Use your tools before forming an opinion. "
                    "Output a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Marketing",
                evaluation_dimension="Customer acquisition & positioning",
                system_prompt=(
                    "You are a marketing lead. Evaluate each option for "
                    "customer acquisition difficulty and positioning "
                    "strength. Use your tools before forming an opinion. "
                    "Output a score 1-10 and concise reasoning."
                ),
            ),
            PersonaConfig(
                agent_name="Finance",
                evaluation_dimension="Cost structure & sustainability",
                system_prompt=(
                    "You are a startup CFO. Evaluate each option for cost "
                    "structure and financial sustainability. Use your tools "
                    "before forming an opinion. Output a score 1-10 and "
                    "concise reasoning."
                ),
            ),
        ],
        enabled_tools=["web_search"],
        starter_prompts=[
            "Should our startup choose subscription or one-time pricing?",
            "Should we raise a seed round now or bootstrap another 6 months?",
        ],
    ),
}


# ---------------------------------------------------------------------------
# 1. CORE DATA MODELS  (owned by the group -- frozen after step 1)
# ---------------------------------------------------------------------------

class Constraints(BaseModel):
    team_size: int
    timeline: str          # e.g. "6 months"
    budget: str | None = None


DebateStatus = Literal[
    "pending",
    "analyzing",       # initial_analysis node running
    "cross_examining", # cross_examination node running
    "consensus",       # moderator_consensus node running
    "complete",
    "failed",
]


class ToolCall(BaseModel):
    tool_name: str          # "web_search" | "github_repo_stats" | "url_fetch" | "document_reader"
    query: str
    result_summary: str     # short summary the agent will reason over


class ToolResult(BaseModel):
    tool_name: str
    query: str
    result_summary: str
    raw_data: dict = Field(default_factory=dict)
    duration_ms: float | None = None


class AgentStance(BaseModel):
    agent_name: str          # must match a PersonaConfig.agent_name from the active preset
    option: str               # which option this stance is about
    score: float               # 1-10
    reasoning: str
    tool_calls_used: list[ToolCall] = Field(default_factory=list)


class CrossExamMessage(BaseModel):
    from_agent: str
    to_agent: str
    challenge: str
    response: str


class OptionResult(BaseModel):
    option: str
    average_score: float
    why_it_lost: str | None = None   # populated for all but the winner


class ConsensusResult(BaseModel):
    winning_option: str
    confidence_pct: float
    agreement_pct: float
    disagreement_pct: float
    risks: list[str]
    option_breakdown: list[OptionResult]
    rationale: str


class DebateRequest(BaseModel):
    preset_id: PresetId                              # NEW in v2.0 -- required on every request
    question: str
    options: list[str] = Field(min_length=2, max_length=4)
    constraints: Constraints


class DebateState(BaseModel):
    """
    THE LANGGRAPH WORKING STATE -- owned by Person A.
    This is what every node in the StateGraph reads from and writes to as
    the debate moves through initial_analysis -> cross_examination ->
    moderator_consensus. NOT the same object as DebateResult below, which
    is the final flattened output once status == "complete".

    preset_id is set once at creation and used to look up
    DOMAIN_REGISTRY[preset_id] for personas/tools -- the graph itself
    never hardcodes persona names, it just iterates whatever the registry
    returns for this preset_id.
    """
    debate_id: str
    preset_id: PresetId                               # NEW in v2.0
    status: DebateStatus = "pending"
    question: str
    options: list[str]
    constraints: Constraints
    user_id: str | None = None                        # NEW in v2.1 -- set by API layer, not graph

    # accumulates as agents finish -- Person D streams each new entry as
    # an `agent_stance` SSE event the moment it's appended
    agent_stances: list[AgentStance] = Field(default_factory=list)

    # accumulates during cross-exam -- streamed as `cross_exam` events
    cross_exam_transcript: list[CrossExamMessage] = Field(default_factory=list)

    # every tool call any agent makes, in order -- streamed as `tool_call` events
    tool_call_log: list[ToolCall] = Field(default_factory=list)

    # only populated once status == "complete"
    consensus: ConsensusResult | None = None

    # only populated if status == "failed"
    error_message: str | None = None


class DebateResult(BaseModel):
    debate_id: str
    preset_id: PresetId                                # NEW in v2.0
    question: str
    options: list[str]
    status: DebateStatus
    agent_stances: list[AgentStance]
    cross_exam_transcript: list[CrossExamMessage]
    consensus: ConsensusResult
    user_id: str | None = None                         # NEW in v2.1


def new_debate_id() -> str:
    """Owned by Person D -- the one place debate IDs get generated.
    Everyone else just treats debate_id as an opaque string."""
    return f"debate_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# 2. FUNCTION SIGNATURES -- the interface each person exposes to the others
#    Build your real logic behind these. Everyone else codes against the
#    stub versions below until your real piece is ready to swap in.
# ---------------------------------------------------------------------------

# --- Owned by Person C (Generic Tools / MCP) --------------------------------

# REAL MCP TOOL DEFINITIONS -- this is what actually gets registered on the
# MCP server and exposed for agent discovery/invocation. The plain Python
# functions below are ONLY for local stubbing/testing by A and B before
# C's real MCP server exists. If this schema isn't what's actually
# registered on the server, you've built helper functions, not MCP tools.
#
# v2.0: three GENERIC tools work for every preset. github_repo_stats is
# the one domain-specific tool -- only bind it to an agent when
# "github_repo_stats" appears in that preset's enabled_tools (today, only
# the Developer preset includes it).

MCP_TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current information relevant to the "
            "decision (benchmarks, comparisons, community opinion, news). "
            "Generic -- available to every preset. Use this before forming "
            "an opinion on any factual claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "url_fetch",
        "description": (
            "Fetch and summarize the content of a specific URL. Generic -- "
            "available to every preset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "document_reader",
        "description": (
            "Read and summarize an uploaded or linked document (PDF, "
            "syllabus, spec). Generic -- available to every preset that "
            "enables it (currently Education)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_url": {"type": "string", "description": "URL or path to the document"}
            },
            "required": ["document_url"],
        },
    },
    {
        "name": "github_repo_stats",
        "description": (
            "Fetch health signals for a GitHub repository: stars, last "
            "commit date, open issue count. DOMAIN-SPECIFIC -- only bind "
            "this tool when the active preset's enabled_tools includes it "
            "(currently Developer only)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo format, e.g. 'facebook/react'"}
            },
            "required": ["repo"],
        },
    },
]

# --- Local stub functions (for A/B to develop against before C's MCP
#     server is live) --------------------------------------------------------

def run_tool_search(query: str) -> ToolResult:
    """STUB -- replace with real Tavily/DuckDuckGo-backed MCP tool call."""
    return ToolResult(
        tool_name="web_search",
        query=query,
        result_summary=f"[stub] Top result summary for: {query}",
        raw_data={},
        duration_ms=0.0,
    )


def run_url_fetch(url: str) -> ToolResult:
    """STUB -- replace with real MCP-backed URL fetch + summarize call."""
    return ToolResult(
        tool_name="url_fetch",
        query=url,
        result_summary=f"[stub] Summary of content at: {url}",
        raw_data={},
        duration_ms=0.0,
    )


def run_document_reader(document_url: str) -> ToolResult:
    """STUB -- replace with real MCP-backed document read + summarize call."""
    return ToolResult(
        tool_name="document_reader",
        query=document_url,
        result_summary=f"[stub] Summary of document: {document_url}",
        raw_data={},
        duration_ms=0.0,
    )


def run_github_repo_stats(repo: str) -> ToolResult:
    """STUB -- replace with real GitHub REST API call.
    DOMAIN-SPECIFIC: only ever invoked when the active preset's
    enabled_tools includes 'github_repo_stats'."""
    return ToolResult(
        tool_name="github_repo_stats",
        query=repo,
        result_summary=f"[stub] {repo}: 12.3k stars, last commit 3 days ago",
        raw_data={"stars": 12300, "last_commit_days_ago": 3},
        duration_ms=0.0,
    )


# --- Owned by Person B (Personas, Scoring & Registry) -----------------------

def run_agent_analysis(
    persona: PersonaConfig,
    question: str,
    options: list[str],
    constraints: Constraints,
) -> list[AgentStance]:
    """STUB -- replace with real Groq-backed agent reasoning + tool calls.
    `persona` comes from DOMAIN_REGISTRY[preset_id].personas -- never
    hardcode persona names/prompts inside this function itself. Returns
    one AgentStance per option."""
    return [
        AgentStance(
            agent_name=persona.agent_name,
            option=opt,
            score=7.0,
            reasoning=f"[stub] {persona.agent_name}'s take on {opt}",
            tool_calls_used=[],
        )
        for opt in options
    ]


def aggregate_scores(
    all_stances: list[AgentStance],
    options: list[str],
    scoring_weights: dict[str, float] | None = None,
) -> ConsensusResult:
    """STUB -- replace with real deterministic aggregation math.
    This should NOT be another LLM call -- pure aggregation logic.
    `scoring_weights` comes from the active preset's registry entry;
    an empty dict means equal weight for every agent."""
    return ConsensusResult(
        winning_option=options[0],
        confidence_pct=72.0,
        agreement_pct=80.0,
        disagreement_pct=20.0,
        risks=["[stub] risk one", "[stub] risk two"],
        option_breakdown=[
            OptionResult(option=o, average_score=7.0,
                         why_it_lost=None if o == options[0] else "[stub] reason")
            for o in options
        ],
        rationale="[stub] moderator rationale text",
    )


# --- Owned by Person A (Orchestration) --------------------------------------

def run_debate(
    debate_id: str,
    preset_id: PresetId,
    question: str,
    options: list[str],
    constraints: Constraints,
) -> DebateResult:
    """STUB -- replace with the real compiled LangGraph invocation.
    This is the single entry point Person D's API calls into. The graph
    looks up DOMAIN_REGISTRY[preset_id] to get its persona list and
    tool list -- it never hardcodes them."""
    preset = DOMAIN_REGISTRY[preset_id]
    stances: list[AgentStance] = []
    for persona in preset.personas:
        stances.extend(run_agent_analysis(persona, question, options, constraints))

    return DebateResult(
        debate_id=debate_id,
        preset_id=preset_id,
        question=question,
        options=options,
        status="complete",
        agent_stances=stances,
        cross_exam_transcript=[
            CrossExamMessage(
                from_agent=preset.personas[0].agent_name,
                to_agent=preset.personas[1].agent_name if len(preset.personas) > 1 else preset.personas[0].agent_name,
                challenge="[stub] challenge",
                response="[stub] response",
            )
        ],
        consensus=aggregate_scores(stances, options, preset.scoring_weights),
    )


# ---------------------------------------------------------------------------
# 3. SSE EVENT SCHEMA -- owned by Person D, consumed by whatever builds the
#    frontend. Event `data` field is always the JSON-encoded payload below.
#    Shape is identical regardless of preset -- only the content inside
#    (agent names, tool names) differs.
# ---------------------------------------------------------------------------

class SSEAgentStanceEvent(BaseModel):
    event: Literal["agent_stance"] = "agent_stance"
    data: AgentStance


class SSEToolCallEvent(BaseModel):
    event: Literal["tool_call"] = "tool_call"
    data: ToolCall


class SSECrossExamEvent(BaseModel):
    event: Literal["cross_exam"] = "cross_exam"
    data: CrossExamMessage


class SSEConsensusEvent(BaseModel):
    event: Literal["consensus_final"] = "consensus_final"
    data: ConsensusResult


class SSEErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    data: dict  # {"message": str, "recoverable": bool}


"""
Example raw SSE stream for a Developer-preset debate (Education/Startup
follow the identical shape, just with different agent_name/tool_name
values pulled from their own preset):

event: agent_stance
data: {"agent_name": "Architect", "option": "Postgres", "score": 8.0,
       "reasoning": "...", "tool_calls_used": []}

event: tool_call
data: {"tool_name": "github_repo_stats", "query": "postgres/postgres",
       "result_summary": "18.2k stars, last commit 1 day ago"}

event: cross_exam
data: {"from_agent": "Security", "to_agent": "Architect",
       "challenge": "...", "response": "..."}

event: consensus_final
data: {"winning_option": "Postgres", "confidence_pct": 84.0, ...}
"""


# ---------------------------------------------------------------------------
# 4. API ENDPOINTS -- owned by Person D. Everyone else can assume these exist.
# ---------------------------------------------------------------------------

"""
GET /presets
  returns: list[PresetConfig]   (NEW in v2.0 -- powers the preset selector UI)

POST /debate
  body: DebateRequest   (now requires preset_id)
  returns: {"debate_id": str}

GET /debate/{debate_id}/stream
  returns: text/event-stream of SSE events defined in section 3, in order,
  terminated by a "consensus_final" event.

GET /debate/{debate_id}/result
  returns: DebateResult  (for polling/fallback if SSE isn't used)
"""


# ---------------------------------------------------------------------------
# 5. SHARED ENV CONFIG -- copy this to a real .env, never commit real values.
#    Everyone uses these exact variable names so nothing is hardcoded
#    differently between the 4 people's machines/modules.
# ---------------------------------------------------------------------------

"""
.env.example
------------
GROQ_API_KEY=
GROQ_MODEL_PRIMARY=llama-3.3-70b-versatile
GROQ_MODEL_FALLBACK=llama-3.1-8b-instant

TAVILY_API_KEY=
GITHUB_TOKEN=                      # optional, raises unauthenticated rate limit

API_BASE_URL=http://localhost:8000  # frontend points here; swap when deployed
CORS_ALLOWED_ORIGINS=http://localhost:3000

DEBATE_CROSS_EXAM_ROUNDS=1          # keep at 1 -- do not make this unbounded
"""
