-- ARTHA SETU -- auth schema (users, sessions).
--
-- A NEW file, separate from schema.sql -- see db/init_auth_db.py. Safe to
-- re-run (CREATE ... IF NOT EXISTS). Requires pgcrypto (gen_random_uuid()).
--
-- Design note: per FronteEnd's actual sign-up/login UI ("Your name becomes
-- your login handle"), there's no separate username field -- `name` IS the
-- unique login handle. Revised from an earlier draft that had a distinct
-- `username` column, once FronteEnd's real contract was known.

CREATE TABLE IF NOT EXISTS users (
    user_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL UNIQUE,   -- display name AND login handle
    password_hash           TEXT NOT NULL,          -- PBKDF2-HMAC-SHA256 hex digest
    password_salt           TEXT NOT NULL,          -- per-user random salt, hex
    age                     INTEGER NOT NULL CHECK (age BETWEEN 18 AND 100),
    business_category       TEXT NOT NULL,
    company_size            TEXT NOT NULL,          -- declared scale (e.g. Solo/2-5/6-20/20+, matches FronteEnd's select)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_name_lower ON users (lower(name));

-- Bearer token issued on signup/login. Not yet enforced anywhere (no
-- endpoint currently requires it) -- FronteEnd stores it client-side per
-- its own "artha-token" localStorage key; this table makes the token real
-- and revocable rather than a value nobody can verify.
CREATE TABLE IF NOT EXISTS sessions (
    token          TEXT PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES users(user_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
