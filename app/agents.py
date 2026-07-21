import os
import json
import re
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# Import the agreed-upon schemas from the shared contract
from .contracts import (
    AgentStance,
    Constraints,
    ToolCall,
    PersonaConfig,
    CrossExamMessage,
    DebateState,
    PresetId,
)

load_dotenv()
logger = logging.getLogger(__name__)

# 1. GROQ CLIENT WRAPPER WITH FALLBACK
def get_llm():
    """Returns a Groq LLM client that automatically falls back on 429 rate limits."""
    if not os.getenv("GROQ_API_KEY"):
        return _DeterministicLLM()

    primary_model = os.getenv("GROQ_MODEL_PRIMARY", "llama-3.3-70b-versatile")
    fallback_model = os.getenv("GROQ_MODEL_FALLBACK", "llama-3.1-8b-instant")
    
    primary_llm = ChatGroq(model=primary_model, temperature=0.2, max_retries=1)
    fallback_llm = ChatGroq(model=fallback_model, temperature=0.2, max_retries=2)
    
    # Langchain's built-in fallback mechanism prevents crashing if the free tier rate-limits
    return primary_llm.with_fallbacks([fallback_llm])


class _DeterministicResponse:
    def __init__(self, content: str):
        self.content = content


class _DeterministicLLM:
    """Local fallback used when GROQ_API_KEY is absent in tests or demos."""

    def invoke(self, messages):
        text = "\n".join(str(getattr(message, "content", message)) for message in messages)
        options = _extract_options_from_prompt(text)
        agent_name = _extract_agent_name_from_prompt(text)
        if options:
            payload = [
                {
                    "agent_name": agent_name,
                    "option": option,
                    "score": max(6.0, 8.0 - index * 0.4),
                    "reasoning": (
                        f"{agent_name} gives {option} a pragmatic score based on "
                        "the supplied constraints and available evidence."
                    ),
                    "tool_calls_used": [],
                }
                for index, option in enumerate(options)
            ]
            return _DeterministicResponse(json.dumps(payload))
        return _DeterministicResponse(
            "This challenge is valid, but the original assessment still holds under the stated constraints."
        )


def _extract_agent_name_from_prompt(text: str) -> str:
    match = re.search(r'"agent_name":\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"You are ([^.\\n]+)", text)
    if match:
        return match.group(1).strip()
    return "Agent"


def _extract_options_from_prompt(text: str) -> list[str]:
    match = re.search(r"Evaluate the following options:\s*(.*?)\.", text, re.DOTALL)
    if not match:
        return []
    return [option.strip() for option in match.group(1).split(",") if option.strip()]


def _resolve_preset_id_for_persona(persona: PersonaConfig) -> PresetId | None:
    """Find the active preset through the registry without hardcoded domains."""

    from .registry import DOMAIN_REGISTRY

    for preset_id, preset in DOMAIN_REGISTRY.items():
        for configured_persona in preset.personas:
            if configured_persona == persona:
                return preset_id
    return None


def _collect_tool_evidence(
    persona: PersonaConfig,
    question: str,
    options: list[str],
) -> list[ToolCall]:
    """Collect one generic tool evidence item through Person C's enabled gate."""

    preset_id = _resolve_preset_id_for_persona(persona)
    if preset_id is None:
        return []

    from .tools_mcp import call_enabled_tool, get_enabled_tool_names

    enabled_tools = get_enabled_tool_names(preset_id)
    if "web_search" not in enabled_tools:
        return []

    query = f"{question} {' vs '.join(options)} {persona.evaluation_dimension}".strip()
    if os.getenv("DEBATESTACK_ENABLE_EXTERNAL_TOOLS") != "1":
        return [
            ToolCall(
                tool_name="web_search",
                query=query,
                result_summary=(
                    "web_search execution skipped because DEBATESTACK_ENABLE_EXTERNAL_TOOLS "
                    "is not enabled; tool access was resolved through the preset gate."
                ),
            )
        ]

    try:
        result = call_enabled_tool(preset_id, "web_search", query=query)
    except Exception as exc:
        if os.getenv("DEBATESTACK_STRICT_TOOLS") == "1":
            raise
        result = None

    if result is None:
        return [
            ToolCall(
                tool_name="web_search",
                query=query,
                result_summary="web_search unavailable during local execution; continuing without external evidence.",
            )
        ]

    return [
        ToolCall(
            tool_name=result.tool_name,
            query=result.query,
            result_summary=result.result_summary,
        )
    ]

def normalize_option(returned_option: str, official_options: list[str]) -> str:
    if not returned_option:
        return official_options[0] if official_options else ""
        
    returned_option_str = str(returned_option).strip()
    
    # 1. Exact match
    if returned_option_str in official_options:
        return returned_option_str
        
    # 2. Case-insensitive exact match
    ret_lower = returned_option_str.lower()
    for opt in official_options:
        if opt.strip().lower() == ret_lower:
            return opt
            
    # 3. Substring match
    for opt in official_options:
        opt_lower = opt.strip().lower()
        if opt_lower in ret_lower or ret_lower in opt_lower:
            return opt
            
    # 4. Fallback to closest match or first option if completely unmatched
    return official_options[0] if official_options else returned_option_str

def extract_stances_from_json(parsed_json, agent_name: str, options: list[str]) -> list[dict]:
    raw_items = []
    
    if isinstance(parsed_json, list):
        for item in parsed_json:
            if isinstance(item, dict):
                raw_items.append(item)
    elif isinstance(parsed_json, dict):
        # Case 1: The dict is {"stances": [...] } or {"options": [...] }
        found_list = False
        for key in ["stances", "options", "results", "data", "array"]:
            if key in parsed_json and isinstance(parsed_json[key], list):
                for item in parsed_json[key]:
                    if isinstance(item, dict):
                        raw_items.append(item)
                found_list = True
                break
        
        # Case 2: The dict maps options to stance details, e.g. {"PostgreSQL": {"score": 8, "reasoning": "..."}}
        if not found_list:
            for key, val in parsed_json.items():
                if isinstance(val, dict):
                    item_copy = dict(val)
                    if "option" not in item_copy:
                        item_copy["option"] = key
                    raw_items.append(item_copy)
                elif isinstance(val, (int, float)):
                    # Simpler dict, e.g. {"PostgreSQL": 8.0, "MongoDB": 7.0}
                    raw_items.append({
                        "option": key,
                        "score": val,
                        "reasoning": f"Scored {val}/10 by {agent_name}."
                    })
    
    return raw_items

# 2. CORE ANALYSIS FUNCTION
def run_agent_analysis(
    persona: PersonaConfig,
    question: str,
    options: list[str],
    constraints: Constraints,
) -> list[AgentStance]:
    """
    Executes Groq-backed reasoning for a specific agent persona.
    Returns one AgentStance per option, strictly matching the contract.
    """
    llm = get_llm()
    
    persona_prompt = persona.system_prompt
    agent_name = persona.agent_name
    tool_calls_used = _collect_tool_evidence(persona, question, options)
    evidence_summary = "\n".join(
        f"- {tool.tool_name}: {tool.result_summary}" for tool in tool_calls_used
    ) or "No external tool evidence was available."
    
    system_instruction = f"""
    {persona_prompt}
    
    You are evaluating a decision. 
    Question: {question}
    Constraints: Team Size: {constraints.team_size}, Timeline: {constraints.timeline}, Budget: {constraints.budget}
    Tool evidence:
    {evidence_summary}
    
    Evaluate the following options: {', '.join(options)}.
    
    Provide your output as a raw JSON array of objects. The array MUST contain exactly one object for each option listed. Each object MUST exactly match this schema:
    {{
        "agent_name": "{agent_name}",
        "option": "Name of the option",
        "score": (float between 1.0 and 10.0),
        "reasoning": "A concise 1-2 sentence justification",
        "tool_calls_used": []
    }}
    Do NOT wrap the JSON in markdown blocks (e.g., no ```json). Return ONLY the raw JSON array.
    """

    messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content="Evaluate the options and provide the JSON array.")
    ]
    
    response = llm.invoke(messages)
    
    # Parse the JSON response into our Pydantic models
    try:
        raw_output = response.content.strip()
        # Find JSON array or object in the response content
        match = re.search(r"(\[.*\]|\{.*\})", raw_output, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = raw_output
             
        parsed_json = json.loads(json_str.strip())
        raw_items = extract_stances_from_json(parsed_json, agent_name, options)
        
        stances = []
        for item in raw_items:
            # 1. Force agent_name to match
            item["agent_name"] = agent_name
            
            # 2. Normalize option
            opt_val = item.get("option", "")
            item["option"] = normalize_option(opt_val, options)
            
            # 3. Clean score and clamp to [1.0, 10.0]
            try:
                score_val = float(item.get("score", 5.0))
                item["score"] = max(1.0, min(10.0, score_val))
            except (ValueError, TypeError):
                item["score"] = 5.0
                
            # 4. Clean reasoning
            if "reasoning" not in item or not item["reasoning"]:
                item["reasoning"] = f"No reasoning provided by {agent_name}."
            else:
                item["reasoning"] = str(item["reasoning"])
                
            # 5. Clean tool_calls_used
            if "tool_calls_used" not in item or not isinstance(item["tool_calls_used"], list):
                item["tool_calls_used"] = []
            else:
                cleaned_calls = []
                for tc in item["tool_calls_used"]:
                    if isinstance(tc, dict):
                        cleaned_calls.append({
                            "tool_name": str(tc.get("tool_name", "web_search")),
                            "query": str(tc.get("query", "")),
                            "result_summary": str(tc.get("result_summary", ""))
                        })
                item["tool_calls_used"] = cleaned_calls
            if not item["tool_calls_used"] and tool_calls_used and item["option"] == options[0]:
                item["tool_calls_used"] = [
                    {
                        "tool_name": tool.tool_name,
                        "query": tool.query,
                        "result_summary": tool.result_summary,
                    }
                    for tool in tool_calls_used
                ]
                
            try:
                stance = AgentStance(**item)
                stances.append(stance)
            except Exception as ve:
                logger.warning(
                    "Agent stance validation error: agent=%s item=%s error=%s",
                    agent_name,
                    item,
                    ve,
                )
                
        # Ensure there is exactly one stance for each option
        existing_options = {s.option for s in stances}
        for opt in options:
            if opt not in existing_options:
                stances.append(
                    AgentStance(
                        agent_name=agent_name,
                        option=opt,
                        score=5.0,
                        reasoning=f"Neutral default stance for {opt} due to incomplete evaluation.",
                        tool_calls_used=tool_calls_used if opt == options[0] else []
                    )
                )
                
        # Return only the stances for the requested options (filter out any duplicates or extra options)
        final_stances = []
        seen_options = set()
        for s in stances:
            if s.option in options and s.option not in seen_options:
                final_stances.append(s)
                seen_options.add(s.option)
        return final_stances
        
    except Exception as e:
        # Graceful degradation: return neutral stubs if parsing fails completely
        logger.exception(
            "Agent response parsing failed; returning neutral stances: agent=%s output=%s",
            agent_name,
            response.content,
        )
        return [
            AgentStance(
                agent_name=agent_name, 
                option=opt, 
                score=5.0, 
                reasoning="Error parsing LLM response. Defaulting to neutral score.",
                tool_calls_used=tool_calls_used if opt == options[0] else []
            ) for opt in options
        ]


def run_cross_examination(state: DebateState) -> list[CrossExamMessage]:
    """
    Executes one round of cross-examination between agents.
    Each agent challenges one other agent's stance on a shared option,
    and the challenged agent responds. Returns the full transcript.
    """
    llm = get_llm()

    stances = state.agent_stances
    if len(stances) < 2:
        return []

    agent_names = list({s.agent_name for s in stances})
    options = state.options
    transcript: list[CrossExamMessage] = []

    for i in range(len(agent_names)):
        challenger_name = agent_names[i]
        responder_name = agent_names[(i + 1) % len(agent_names)]

        challenger_stances = {s.option: s for s in stances if s.agent_name == challenger_name}
        responder_stances = {s.option: s for s in stances if s.agent_name == responder_name}

        shared_options = [o for o in options if o in challenger_stances and o in responder_stances]
        if not shared_options:
            continue

        target_option = shared_options[0]
        challenger = challenger_stances[target_option]
        responder = responder_stances[target_option]

        challenge_prompt = f"""
        You are {challenger_name}. You scored option "{target_option}" {challenger.score}/10.
        Another agent ({responder_name}) scored it {responder.score}/10.
        Their reasoning: {responder.reasoning}

        Challenge their assessment with a sharp, specific question or critique
        in 1-2 sentences. Be direct and substantive.
        """

        challenge_resp = llm.invoke([HumanMessage(content=challenge_prompt)])
        challenge_text = challenge_resp.content.strip()

        response_prompt = f"""
        You are {responder_name}. You scored option "{target_option}" {responder.score}/10.
        {challenger_name} challenged you: "{challenge_text}"

        Respond to their challenge in 1-2 sentences. Be direct and defend
        or revise your position.
        """

        response_resp = llm.invoke([HumanMessage(content=response_prompt)])
        response_text = response_resp.content.strip()

        transcript.append(CrossExamMessage(
            from_agent=challenger_name,
            to_agent=responder_name,
            challenge=challenge_text,
            response=response_text,
        ))

    return transcript
