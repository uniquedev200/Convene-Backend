# Convene Backend

Multi-agent debate engine with agentic AI. FastAPI backend that runs structured debates across domain presets using LangGraph, with real-time SSE streaming, hand-rolled auth, and Postgres persistence.

## Quick Start

```bash
# Install
pip install -e ".[test]"

# Set up environment
cp .env.example .env
# Fill in GROQ_API_KEY, JWT_SECRET, SUPABASE_DB_URL

# Create database tables
python -c "import asyncpg, asyncio; exec(open('db/schema.sql').read())"  # or run schema.sql directly

# Run
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API available at `http://127.0.0.1:8000`.

## Architecture

```
POST /debate  →  LangGraph orchestrator  →  4 domain personas (LLM agents)
                   ↕                              ↕
              tool calls (web_search,          cross-examination
              url_fetch, github, docs)         (agent challenges)
                   ↕                              ↕
              scoring + weighting  →  consensus finalization  →  SSE stream
```

**Presets:** `developer`, `education`, `startup` — each with unique personas, tools, and scoring weights. Domain-agnostic graph structure.

## Auth

Hand-rolled email+password flow (no Supabase Auth). bcrypt hashing, 6-digit verification codes via Resend, HS256 JWTs.

| Endpoint | Method | Description |
|---|---|---|
| `/auth/signup` | POST | Register with email+password, sends verification code |
| `/auth/verify` | POST | Verify code, get JWT |
| `/auth/login` | POST | Login with email+password, get JWT |

Anonymous debates work without auth. Authenticated debates are stored per-user.

## API

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | No | Health check |
| `/presets` | GET | No | List all debate presets |
| `/tools` | GET | No | List available tools by preset |
| `/debate` | POST | Yes | Create and start a debate |
| `/debate/{id}/stream` | GET | No | SSE stream of live debate events |
| `/debate/{id}/result` | GET | No | Final debate result |
| `/debates/mine` | GET | Yes | List authenticated user's debates |

**SSE events:** `agent_stance`, `tool_call`, `cross_exam`, `consensus_final`, `error`

## Database

Postgres via asyncpg. Schema in `db/schema.sql`.

- `users` — email, password_hash, verified
- `verification_codes` — email, code, expires_at
- `debates` — id, user_id, preset_id, question, options, status, result

## Testing

```bash
pytest -q                    # 61 tests
pytest tests/test_api.py     # API integration tests
pytest tests/test_graph.py   # Graph orchestration tests
```

## Environment Variables

See `.env.example` for the full list. Required:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for LLM inference |
| `JWT_SECRET` | Secret for signing JWTs (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `SUPABASE_DB_URL` | Postgres connection string (e.g. `postgresql://...@...pooler.supabase.com:5432/postgres`) |

## Deploy

```bash
docker build -t convene-backend .
docker run -p 8000:8000 --env-file .env convene-backend
```
