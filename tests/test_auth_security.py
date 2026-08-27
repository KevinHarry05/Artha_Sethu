"""
modules/auth/security.py -- pure functions, no DB, no network. The rest of
modules/auth (signup/login) needs a live Postgres connection (see
db/init_auth_db.py) so those are exercised via db/auth_schema.sql +
db/init_auth_db.py + a live server, not here -- consistent with how this
project's other DB-backed modules (location_resolver, etc.) are tested.
"""

from modules.auth.security import hash_password, verify_password


def test_hash_is_not_the_plaintext_password():
    password_hash, salt = hash_password("correct-horse-battery-staple")
    assert password_hash != "correct-horse-battery-staple"
    assert len(salt) == 32  # 16 bytes, hex-encoded


def test_same_password_different_salts_produce_different_hashes():
    hash1, salt1 = hash_password("same-password")
    hash2, salt2 = hash_password("same-password")
    assert salt1 != salt2
    assert hash1 != hash2


def test_verify_password_accepts_correct_password():
    password_hash, salt = hash_password("my-real-password")
    assert verify_password("my-real-password", password_hash, salt) is True


def test_verify_password_rejects_wrong_password():
    password_hash, salt = hash_password("my-real-password")
    assert verify_password("a-guess", password_hash, salt) is False


def test_verify_password_rejects_wrong_salt():
    password_hash, _ = hash_password("my-real-password")
    _, other_salt = hash_password("unrelated")
    assert verify_password("my-real-password", password_hash, other_salt) is False
