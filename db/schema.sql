-- DebateStack database schema
-- Run against Postgres (Supabase or standalone)

-- Users table for hand-rolled email+password auth
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    verified       BOOLEAN NOT NULL DEFAULT false,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- Verification codes for email signup
CREATE TABLE IF NOT EXISTS verification_codes (
    email       TEXT NOT NULL,
    code        TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON verification_codes(email);

-- Debates table
CREATE TABLE IF NOT EXISTS debates (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,
    preset_id   TEXT NOT NULL,
    question    TEXT NOT NULL,
    options     JSONB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_debates_user_id ON debates (user_id);
CREATE INDEX IF NOT EXISTS idx_debates_created_at ON debates (created_at DESC);
