"""Gyaan AI - Authentication and Cryptographic Utilities.

Provides secure password hashing via standard-library hashlib.scrypt,
cryptographically random opaque session tokens, token hashing via SHA-256,
and email normalization.
Zero third-party cryptographic dependencies required.
"""

import hashlib
import hmac
import re
import secrets
from typing import Tuple

# Scrypt parameters recommended for interactive logins (RFC 7914 compliant)
SCRYPT_N = 16384  # CPU/memory cost
SCRYPT_R = 8      # Block size
SCRYPT_P = 1      # Parallelization parameter
SALT_BYTES = 16   # 128-bit cryptographically secure salt
KEY_BYTES = 64    # 512-bit derived key length
MAX_MEM = 64 * 1024 * 1024  # 64 MB maximum RAM limit


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and stripped of whitespace."""
    if not email:
        raise ValueError("Email address cannot be empty.")
    normalized = email.strip().lower()
    # Basic RFC 5322 compliant regex check
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, normalized):
        raise ValueError(f"Invalid email format: '{email}'")
    return normalized


def hash_password(password: str) -> str:
    """Hash a plaintext password using hashlib.scrypt with a random 16-byte salt.

    Returns:
        str: Serialized format 'scrypt:N:r:p:salt_hex:key_hex'
    """
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters in length.")
    if len(password) > 128:
        raise ValueError("Password exceeds maximum allowed length (128 characters).")

    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=MAX_MEM,
        dklen=KEY_BYTES,
    )
    return ":".join([
        "scrypt",
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        salt.hex(),
        derived_key.hex(),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against the stored scrypt hash using constant-time comparison."""
    if not password or not stored_hash:
        return False

    try:
        parts = stored_hash.split(":")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False

        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected_key = bytes.fromhex(parts[5])

        computed_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=MAX_MEM,
            dklen=len(expected_key),
        )
        return hmac.compare_digest(expected_key, computed_key)
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a high-entropy, opaque URL-safe session token (256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def hash_session_token(raw_token: str) -> str:
    """Hash an opaque session token using SHA-256 for secure database storage.

    The raw token is never persisted in SQLite; only this one-way hash is saved.
    """
    if not raw_token:
        raise ValueError("Raw token cannot be empty.")
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
