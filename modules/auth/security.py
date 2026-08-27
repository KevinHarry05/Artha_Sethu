"""
Password hashing -- stdlib only (PBKDF2-HMAC-SHA256), consistent with this
project's "pure Python, minimal dependencies" convention (see requirements.txt
comment: "Financial engine: pure Python + decimal, no numpy for money").
No bcrypt/passlib/argon2 dependency added; hashlib.pbkdf2_hmac is part of
the Python standard library and is an accepted, non-deprecated choice for
password storage when iteration count is kept high (OWASP recommends
>=600,000 for PBKDF2-SHA256 as of 2023 guidance; kept configurable below).
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ITERATIONS = 260_000
_SALT_BYTES = 16
_HASH_NAME = "sha256"


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Returns (password_hash_hex, salt_hex). Generates a fresh random salt
    if one isn't supplied (the normal signup path); a caller-supplied salt
    is only used by verify_password below."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, _ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash_hex: str, salt_hex: str) -> bool:
    """Constant-time comparison (hmac.compare_digest) -- never use == on
    secrets, it leaks timing information about how many leading bytes matched."""
    salt = bytes.fromhex(salt_hex)
    candidate_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(candidate_hash, password_hash_hex)
