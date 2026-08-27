"""
AUTH -- signup / login.

Sits beside the 0 -> gate -> 2a -> 1 -> 2b pipeline, at the API layer --
nothing in pipeline.py changes for this.

Field contract matches FronteEnd's actual built UI exactly (see
api/auth_routes.py for the HTTP layer):
  - Sign up: name, age, business_category, company_size, password.
    "Your name becomes your login handle" is FronteEnd's own copy -- there
    is no separate username; `name` is the unique login field.
  - Log in: name, password.
  - Both return {access_token, user}, matching FronteEnd's
    `onAuth(data.access_token, data.user)` call.

ASSUMPTIONS/DECISIONS (flagged, not silently guessed):
  - Password minimum is 4 characters, matching FronteEnd's own stated
    policy ("Minimum 4 characters.") exactly -- so signup never succeeds
    client-side only to be rejected by the server. This is weak by normal
    standards; if that's not intentional, tighten FRONTEND's hint text and
    MIN_PASSWORD_LENGTH below together, in the same change.
  - business_category is still validated against Dairy/Retail/Textiles --
    the three options FronteEnd's own select actually offers.
  - A real bearer token is issued and stored in `sessions` (see
    db/auth_schema.sql) so it's verifiable later, but nothing currently
    requires it on any other endpoint -- FronteEnd stores it but doesn't
    send it back on `/assess`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from db.connection import get_cursor
from modules.auth.security import hash_password, verify_password

VALID_BUSINESS_CATEGORIES = ("Dairy", "Retail", "Textiles")
MIN_AGE = 18
MAX_AGE = 100
MIN_PASSWORD_LENGTH = 4
SESSION_TOKEN_BYTES = 32


class AuthValidationError(Exception):
    """Bad input -- surfaces as an HTTP 400, never a stack trace."""


class UsernameTakenError(Exception):
    """Surfaces as an HTTP 409 (conflict). Named for the concept, not the
    column -- the unique field is `name`."""


class InvalidCredentialsError(Exception):
    """Surfaces as an HTTP 401. Deliberately the SAME error/message whether
    the name doesn't exist or the password is wrong -- distinguishing the
    two lets an attacker enumerate valid accounts."""


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    name: str
    age: int
    business_category: str
    company_size: str


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    user: UserProfile


def _validate_signup_fields(name: str, age: int, business_category: str, company_size: str, password: str) -> list[str]:
    reasons = []
    if not name.strip():
        reasons.append("Name is required.")
    if not (MIN_AGE <= age <= MAX_AGE):
        reasons.append(f"Age must be between {MIN_AGE} and {MAX_AGE}.")
    if business_category not in VALID_BUSINESS_CATEGORIES:
        reasons.append(f"Unknown business category '{business_category}'. Must be one of {VALID_BUSINESS_CATEGORIES}.")
    if not company_size.strip():
        reasons.append("Company size is required.")
    if len(password) < MIN_PASSWORD_LENGTH:
        reasons.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return reasons


def _create_session(cur, user_id: str) -> str:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    cur.execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
    return token


def signup(name: str, age: int, business_category: str, company_size: str, password: str) -> AuthResult:
    reasons = _validate_signup_fields(name, age, business_category, company_size, password)
    if reasons:
        raise AuthValidationError(" ".join(reasons))

    password_hash, salt = hash_password(password)

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM users WHERE lower(name) = lower(%s)", (name,))
        if cur.fetchone():
            raise UsernameTakenError(f"An account named '{name}' already exists.")

        cur.execute(
            """
            INSERT INTO users (name, password_hash, password_salt, age, business_category, company_size)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id, name, age, business_category, company_size
            """,
            (name.strip(), password_hash, salt, age, business_category, company_size.strip()),
        )
        row = cur.fetchone()
        token = _create_session(cur, row["user_id"])

    profile = UserProfile(
        user_id=str(row["user_id"]), name=row["name"], age=row["age"],
        business_category=row["business_category"], company_size=row["company_size"],
    )
    return AuthResult(access_token=token, user=profile)


def login(name: str, password: str) -> AuthResult:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "SELECT user_id, name, password_hash, password_salt, age, business_category, company_size "
            "FROM users WHERE lower(name) = lower(%s)",
            (name,),
        )
        row = cur.fetchone()

        if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
            raise InvalidCredentialsError("Incorrect name or password.")

        token = _create_session(cur, row["user_id"])

    profile = UserProfile(
        user_id=str(row["user_id"]), name=row["name"], age=row["age"],
        business_category=row["business_category"], company_size=row["company_size"],
    )
    return AuthResult(access_token=token, user=profile)
