"""Persistent debate storage via asyncpg to Supabase Postgres.

Failures never block or crash a debate — log and continue.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_pool: Any = None


async def get_pool() -> Any:
    """Return the shared asyncpg connection pool, creating it lazily."""
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.getenv("SUPABASE_DB_URL")
    if not dsn:
        return None
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
        logger.info("Connected to Supabase Postgres")
        return _pool
    except Exception:
        logger.exception("Failed to connect to Supabase Postgres")
        _pool = None
        return None


async def close_pool() -> None:
    """Shut down the connection pool gracefully."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            logger.exception("Error closing connection pool")
        _pool = None


async def save_debate(
    debate_id: str,
    user_id: str | None,
    preset_id: str,
    question: str,
    options: list[str],
) -> None:
    """Persist a newly created debate. Never raises."""
    pool = await get_pool()
    if pool is None:
        return
    try:
        await pool.execute(
            """
            INSERT INTO debates (id, user_id, preset_id, question, options, status, created_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', now())
            ON CONFLICT (id) DO NOTHING
            """,
            debate_id,
            user_id,
            preset_id,
            question,
            json.dumps(options),
        )
    except Exception:
        logger.exception("Failed to save debate %s", debate_id)


async def update_debate_status(debate_id: str, status: str) -> None:
    """Update debate status. Never raises."""
    pool = await get_pool()
    if pool is None:
        return
    try:
        await pool.execute(
            "UPDATE debates SET status = $1 WHERE id = $2",
            status,
            debate_id,
        )
    except Exception:
        logger.exception("Failed to update status for debate %s", debate_id)


async def update_debate_result(debate_id: str, result: dict) -> None:
    """Persist the final debate result. Raises on failure so caller can retry."""
    pool = await get_pool()
    if pool is None:
        raise RuntimeError("Database pool not available")
    await pool.execute(
        "UPDATE debates SET status = 'complete', result = $1 WHERE id = $2",
        json.dumps(result),
        debate_id,
    )


async def list_debates_for_user(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent debates for a user. Never raises (returns empty list on error)."""
    pool = await get_pool()
    if pool is None:
        return []
    try:
        rows = await pool.fetch(
            """
            SELECT id, preset_id, question, status, created_at
            FROM debates
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to list debates for user %s", user_id)
        return []


async def get_debate_owner(debate_id: str) -> str | None:
    """Return the user_id that owns a debate, or None. Never raises."""
    pool = await get_pool()
    if pool is None:
        return None
    try:
        row = await pool.fetchrow(
            "SELECT user_id FROM debates WHERE id = $1",
            debate_id,
        )
        if row is None:
            return None
        return row["user_id"]
    except Exception:
        logger.exception("Failed to get owner for debate %s", debate_id)
        return None


async def get_debate_from_db(debate_id: str) -> dict | None:
    """Load a full debate row (including result JSON) from the database. Never raises."""
    pool = await get_pool()
    if pool is None:
        return None
    try:
        row = await pool.fetchrow(
            "SELECT id, user_id, preset_id, question, options, status, result, created_at FROM debates WHERE id = $1",
            debate_id,
        )
        if row is None:
            return None
        d = dict(row)
        if d.get("result") and isinstance(d["result"], str):
            d["result"] = json.loads(d["result"])
        if d.get("options") and isinstance(d["options"], str):
            d["options"] = json.loads(d["options"])
        return d
    except Exception:
        logger.exception("Failed to load debate %s from DB", debate_id)
        return None
