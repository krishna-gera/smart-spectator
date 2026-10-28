"""
Smart Spectator - Secure Password Hashing & Verification
Uses PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salt.
Zero external native dependencies; robust across all platforms.
"""

import hashlib
import hmac
import secrets
from typing import Tuple

PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 16


def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    """
    Hashes a password with PBKDF2-HMAC-SHA256.
    Returns (hex_hash, hex_salt).
    """
    if not salt:
        salt = secrets.token_hex(SALT_BYTES)
        
    salt_bytes = bytes.fromhex(salt)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS
    )
    return derived.hex(), salt


def verify_password(plain_password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Constant-time verification of password against stored hash and salt.
    """
    computed_hash, _ = hash_password(plain_password, stored_salt)
    return hmac.compare_digest(computed_hash, stored_hash)
