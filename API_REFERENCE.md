# DebateStack Frontend API Reference

Base URL: `http://localhost:8000` (local) or your deployed URL.

All request/response bodies are JSON. Set `Content-Type: application/json` on every request.

---

## Authentication

All auth endpoints are under `/auth`. Authentication is required for debate creation, history, and result/stream access.

Pass the JWT as a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens expire after 72 hours (configurable server-side). No refresh flow — user re-authenticates on expiry.

---

## Auth Endpoints

### `POST /auth/signup`

Register a new account. Returns a JWT immediately.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `email` | string | yes | Valid email format |
| `password` | string | yes | 8-128 characters |

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "18dfc38e-acd0-4ef2-9677-d7ea4afd4ca7"
}
```

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `409` | `"Email already registered"` | Email exists in DB |
| `422` | Validation error | Invalid email format or password too short |
| `429` | `"Too many signups from this IP. Try again later."` | >3 signups per hour from same IP |
| `503` | `"Database not available"` | DB connection failed |

---

### `POST /auth/login`

Login with email and password.

**Request:**

```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

| Field | Type | Required |
|-------|------|----------|
| `email` | string | yes |
| `password` | string | yes |

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "18dfc38e-acd0-4ef2-9677-d7ea4afd4ca7"
}
```

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `"Invalid email or password"` | Wrong credentials |
| `503` | `"Database not available"` | DB connection failed |

---

## Public Endpoints (No Auth)

### `GET /health`

Health check. Use for monitoring/liveness probes.

**Response `200`:**

```json
{
  "status": "ok",
  "version": "2.1",
  "presets": 3,
  "tools": 4,
  "graph": "loaded",
  "agents": "loaded"
}
```

`graph` and `agents` are `"loaded"` when the real implementations are active, `"stub"` when using fallbacks.

---

### `GET /presets`

List all available debate presets with their personas, tools, and starter prompts.

**Response `200`:**

```json
[
  {
    "preset_id": "developer",
    "display_name": "Developer",
    "personas": [
      {
        "agent_name": "Architect",
        "evaluation_dimension": "Scalability & maintainability",
        "system_prompt": "..."
      },
      {
        "agent_name": "Security",
        "evaluation_dimension": "Attack surface & compliance",
        "system_prompt": "..."
      },
      {
        "agent_name": "Performance",
        "evaluation_dimension": "Latency, throughput & cost",
        "system_prompt": "..."
      },
      {
        "agent_name": "ProductDX",
        "evaluation_dimension": "Developer experience & iteration speed",
        "system_prompt": "..."
      }
    ],
    "enabled_tools": ["web_search", "github_repo_stats", "url_fetch"],
    "scoring_weights": {},
    "starter_prompts": [
      "Postgres vs MongoDB for a 3-person team, 6-month MVP",
      "Monolith vs microservices for a 5-engineer startup"
    ]
  },
  {
    "preset_id": "education",
    "display_name": "Education",
    "personas": [
      { "agent_name": "Professor", ... },
      { "agent_name": "IndustryEngineer", ... },
      { "agent_name": "Recruiter", ... },
      { "agent_name": "ResearchScientist", ... }
    ],
    "enabled_tools": ["web_search", "document_reader"],
    "scoring_weights": {},
    "starter_prompts": [
      "Should a student learn Rust or Go?",
      "Which final-year project should I build: a compiler or a distributed database?"
    ]
  },
  {
    "preset_id": "startup",
    "display_name": "Startup",
    "personas": [
      { "agent_name": "Investor", ... },
      { "agent_name": "Founder", ... },
      { "agent_name": "Marketing", ... },
      { "agent_name": "Finance", ... }
    ],
    "enabled_tools": ["web_search"],
    "scoring_weights": {},
    "starter_prompts": [
      "Should our startup choose subscription or one-time pricing?",
      "Should we raise a seed round now or bootstrap another 6 months?"
    ]
  }
]
```

---

### `GET /tools`

List available tools with which presets they belong to.

**Response `200`:**

```json
[
  {
    "name": "web_search",
    "description": "Search the web for current information...",
    "arguments": {
      "query": { "type": "string", "description": "Search query" }
    },
    "presets": ["developer", "education", "startup"]
  },
  {
    "name": "url_fetch",
    "description": "Fetch and summarize the content of a specific URL...",
    "arguments": {
      "url": { "type": "string", "description": "The URL to fetch" }
    },
    "presets": ["developer"]
  },
  {
    "name": "document_reader",
    "description": "Read and summarize an uploaded or linked document...",
    "arguments": {
      "document_url": { "type": "string", "description": "URL or path to the document" }
    },
    "presets": ["education"]
  },
  {
    "name": "github_repo_stats",
    "description": "Fetch health signals for a GitHub repository...",
    "arguments": {
      "repo": { "type": "string", "description": "owner/repo format, e.g. 'facebook/react'" }
    },
    "presets": ["developer"]
  }
]
```

---

## Debate Endpoints

### `POST /debate`

Start a new debate. Returns immediately with a `debate_id`. The debate runs in the background — poll `/result` or connect to `/stream` for output.

**Auth:** Required. Pass `Authorization: Bearer <token>` in the header.

**Request:**

```json
{
  "preset_id": "developer",
  "question": "Should a 3-person startup use Postgres or MongoDB for their 6-month MVP?",
  "options": ["Postgres", "MongoDB"],
  "constraints": {
    "team_size": 3,
    "timeline": "6 months",
    "budget": "low"
  }
}
```

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `preset_id` | string | yes | One of: `"developer"`, `"education"`, `"startup"` |
| `question` | string | yes | The decision being debated |
| `options` | string[] | yes | 2-4 options to compare |
| `constraints.team_size` | int | yes | Team size |
| `constraints.timeline` | string | yes | e.g. `"6 months"` |
| `constraints.budget` | string | no | e.g. `"low"`, `"lean"` |

**Response `200`:**

```json
{
  "debate_id": "debate_85db6664ea07",
  "stream_url": "http://localhost:8000/debate/debate_85db6664ea07/stream",
  "result_url": "http://localhost:8000/debate/debate_85db6664ea07/result"
}
```

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `"Authentication required"` | No `Authorization` header |
| `401` | `"Invalid token"` / `"Token expired"` | Bad or expired JWT |
| `422` | Validation error | Missing fields, invalid preset_id, or options < 2 / > 4 |
| `429` | `"Rate limit exceeded"` | Too many requests (default: 10/min per user) |
| `503` | `"Server is at capacity. Try again shortly."` | Too many concurrent debates (default: 10) |

---

### `GET /debate/{debate_id}/result`

Get the final result of a debate. Poll this endpoint until `status` is `"complete"`.

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `debate_id` | string | The ID returned by `POST /debate` |

**Response `200` (complete):**

```json
{
  "debate_id": "debate_85db6664ea07",
  "preset_id": "developer",
  "question": "Should a 3-person startup use Postgres or MongoDB for their 6-month MVP?",
  "options": ["Postgres", "MongoDB"],
  "status": "complete",
  "user_id": "18dfc38e-acd0-4ef2-9677-d7ea4afd4ca7",
  "agent_stances": [
    {
      "agent_name": "Architect",
      "option": "Postgres",
      "score": 8.0,
      "reasoning": "Postgres is a well-established relational database with strong ACID compliance...",
      "tool_calls_used": [
        {
          "tool_name": "web_search",
          "query": "Postgres vs MongoDB scalability 2024",
          "result_summary": "Postgres handles complex queries well, MongoDB scales horizontally..."
        }
      ]
    },
    {
      "agent_name": "Architect",
      "option": "MongoDB",
      "score": 6.5,
      "reasoning": "MongoDB is flexible but lacks ACID...",
      "tool_calls_used": []
    },
    {
      "agent_name": "Security",
      "option": "Postgres",
      "score": 8.0,
      "reasoning": "Postgres has mature role-based access control...",
      "tool_calls_used": []
    }
  ],
  "cross_exam_transcript": [
    {
      "from_agent": "Security",
      "to_agent": "Architect",
      "challenge": "You rated Postgres high for maintainability, but what about migration complexity?",
      "response": "Good point. Postgres schema migrations require careful planning..."
    }
  ],
  "consensus": {
    "winning_option": "Postgres",
    "confidence_pct": 80.0,
    "agreement_pct": 100.0,
    "disagreement_pct": 0.0,
    "risks": ["Migration complexity if schema changes frequently"],
    "option_breakdown": [
      {
        "option": "Postgres",
        "average_score": 8.0,
        "why_it_lost": null
      },
      {
        "option": "MongoDB",
        "average_score": 7.1,
        "why_it_lost": "Lower scores on security and maintainability"
      }
    ],
    "rationale": "Postgres scored higher across all four evaluation dimensions..."
  }
}
```

**`user_id`** is `null` for anonymous debates.

**Response `202` (still processing):**

```json
{
  "detail": {
    "status": "analyzing"
  }
}
```

Possible `status` values while processing: `"pending"`, `"analyzing"`, `"cross_examining"`, `"consensus"`.

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `403` | `"Access denied"` | Debate belongs to another user |
| `404` | `"Unknown debate_id"` | Invalid debate ID |
| `502` | Error message string | Debate failed (LLM error, timeout, etc.) |

---

### `GET /debate/{debate_id}/stream`

Real-time Server-Sent Events stream. Connect once after creating a debate and receive events as agents run.

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `debate_id` | string | The ID returned by `POST /debate` |

**Response:** `text/event-stream`

Each event follows SSE format:

```
id: <event_number>
event: <event_type>
data: <json>
```

Keep-alive pings (`: keep-alive`) are sent every 10 seconds while the debate is running.

#### Event Types

**`agent_stance`** — An agent finished evaluating an option.

```json
{
  "agent_name": "Architect",
  "option": "Postgres",
  "score": 8.0,
  "reasoning": "Postgres is a well-established relational database...",
  "tool_calls_used": [
    {
      "tool_name": "web_search",
      "query": "Postgres vs MongoDB scalability",
      "result_summary": "Postgres handles complex queries well..."
    }
  ]
}
```

One event per agent per option. With 4 agents and 2 options, expect 8 `agent_stance` events.

**`tool_call`** — An agent invoked a research tool.

```json
{
  "tool_name": "web_search",
  "query": "Postgres vs MongoDB maintainability 2024",
  "result_summary": "Postgres has stronger guarantees for data integrity..."
}
```

**`cross_exam`** — Two agents exchanged a challenge/response.

```json
{
  "from_agent": "Security",
  "to_agent": "Architect",
  "challenge": "You rated Postgres high for maintainability, but what about migration complexity?",
  "response": "Good point. Postgres schema migrations require careful planning..."
}
```

**`consensus_final`** — The moderator finalized the result. This is the last event.

```json
{
  "winning_option": "Postgres",
  "confidence_pct": 80.0,
  "agreement_pct": 100.0,
  "disagreement_pct": 0.0,
  "risks": ["Migration complexity if schema changes frequently"],
  "option_breakdown": [
    { "option": "Postgres", "average_score": 8.0, "why_it_lost": null },
    { "option": "MongoDB", "average_score": 7.1, "why_it_lost": "Lower scores on security..." }
  ],
  "rationale": "Postgres scored higher across all four evaluation dimensions..."
}
```

**`error`** — Something went wrong.

```json
{
  "message": "Debate failed: LLM timeout",
  "recoverable": false
}
```

#### SSE Stream Order

1. `agent_stance` events (8 total for 4 agents x 2 options, interleaved with tool_call)
2. `tool_call` events (0-8+, embedded within stances)
3. `cross_exam` events (4 rounds for 4 agents)
4. `consensus_final` (terminal event)
5. Stream closes

#### Parsing Tips

```javascript
const source = new EventSource("/debate/debate_85db6664ea07/stream");

source.addEventListener("agent_stance", (e) => {
  const data = JSON.parse(e.data);
  // data.agent_name, data.option, data.score, data.reasoning
});

source.addEventListener("tool_call", (e) => {
  const data = JSON.parse(e.data);
  // data.tool_name, data.query, data.result_summary
});

source.addEventListener("cross_exam", (e) => {
  const data = JSON.parse(e.data);
  // data.from_agent, data.to_agent, data.challenge, data.response
});

source.addEventListener("consensus_final", (e) => {
  const data = JSON.parse(e.data);
  // data.winning_option, data.confidence_pct, data.option_breakdown
  source.close();
});

source.addEventListener("error", (e) => {
  // e.data contains {"message": "...", "recoverable": bool}
});
```

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `403` | `"Access denied"` | Debate belongs to another user |
| `404` | `"Unknown debate_id"` | Invalid debate ID |

---

## Authenticated Endpoints

### `GET /debates/mine`

List the authenticated user's recent debates. Requires `Authorization` header.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response `200`:**

```json
[
  {
    "id": "debate_85db6664ea07",
    "preset_id": "developer",
    "question": "Should a 3-person startup use Postgres or MongoDB?",
    "status": "complete",
    "created_at": "2026-07-20T12:34:56.789Z"
  },
  {
    "id": "debate_a1b2c3d4e5f6",
    "preset_id": "education",
    "question": "Should a student learn Rust or Go?",
    "status": "analyzing",
    "created_at": "2026-07-20T11:22:33.456Z"
  }
]
```

Returns up to 50 most recent debates, ordered newest first. Returns `[]` if no debates or DB error.

**Errors:**

| Status | Detail | Cause |
|--------|--------|-------|
| `401` | `"Authentication required"` | No `Authorization` header |
| `401` | `"Invalid token"` / `"Token expired"` | Bad or expired JWT |

---

## Status Codes Summary

| Code | Meaning |
|------|---------|
| `200` | Success |
| `202` | Debate still processing (poll again) |
| `401` | Not authenticated or invalid/expired token |
| `403` | Authenticated but not the owner of this resource |
| `404` | Resource not found (bad debate_id) |
| `409` | Conflict (email already registered) |
| `422` | Request validation failed (bad body) |
| `429` | Rate limited |
| `500` | Server error (auth not configured) |
| `503` | Server at capacity |
| `503` | Database not available |

---

## Rate Limits & Abuse Protection

- **Debate creation:** 10 per minute per user (JWT-based)
- **Signup:** 3 per hour per IP
- **Concurrent debate cap:** 10 in-flight debates max
- **Session TTL:** completed/failed debates auto-expire from memory after 1 hour
- **Result/stream access:** ownership check — debate owner only (403 if mismatch)

---

## CORS

Allowed origins default to `*` (all origins). Credentials are not sent (no cookies — Bearer tokens used instead).

---

## Typical Frontend Flow

1. `POST /auth/signup` or `POST /auth/login` → store `access_token`
2. `GET /presets` → let user pick a preset and question
3. `POST /debate` (with `Authorization: Bearer <token>`) → get `debate_id`
4. `GET /debate/{debate_id}/stream` → show live agent stances, tool calls, cross-exams
5. On `consensus_final` event → show winner, scores, rationale
6. `GET /debates/mine` → show user's debate history
