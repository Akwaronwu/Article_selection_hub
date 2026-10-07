"""Authentication primitives: password hashing and session tokens.

Passwords use argon2id with OWASP-recommended parameters. Session tokens are
random; only their SHA-256 digest is persisted (docs/SECURITY.md §1).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

# OWASP Password Storage Cheat Sheet: argon2id, m=19 MiB, t=2, p=1.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,
    parallelism=1,
    type=Type.ID,
)


class PasswordPolicyError(ValueError):
    """Raised when a password does not meet the minimum policy."""


def validate_password_policy(password: str) -> None:
    """Enforce minimum password length (10 chars); raise ``PasswordPolicyError``."""
    if len(password) < 10:
        raise PasswordPolicyError("Password must be at least 10 characters long.")


def hash_password(password: str) -> str:
    """Hash a password with argon2id (validates policy first)."""
    validate_password_policy(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-behaviour verification; never raises for wrong passwords."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses outdated parameters."""
    return _hasher.check_needs_rehash(password_hash)


def generate_session_token() -> str:
    """URL-safe 256-bit random session token (raw value → cookie only)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """SHA-256 hex digest of a session token (value stored in the DB)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(ttl_hours: int) -> datetime:
    """Expiry timestamp ``ttl_hours`` in the future (naive UTC)."""
    from app.timeutil import utcnow

    return utcnow() + timedelta(hours=ttl_hours)


def normalize_email(email: str) -> str:
    """Lower-case and strip an email address for storage/comparison."""
    return email.strip().lower()
