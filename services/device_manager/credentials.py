"""
Smart Spectator - Device Credentials & Security Helpers
Follows docs/06_DEVICE_AUTHENTICATION.md and docs/13_SECURITY_MODEL.md
"""

import hmac
import hashlib
import secrets
from typing import Tuple
from ..hub_backend.config import settings


def generate_pairing_pin() -> str:
    """Generates a cryptographically secure 6-digit numeric verification PIN."""
    # Value between 100000 and 999999
    pin_int = secrets.randbelow(900000) + 100000
    return str(pin_int)


def generate_device_token(device_id: str) -> Tuple[str, str]:
    """
    Generates a secure bearer token and its corresponding HMAC-SHA256 hash.
    Returns:
        Tuple of (raw_token, token_hash)
        The raw token is transmitted ONCE to the device and never stored in plaintext.
        The token_hash is persisted in the database.
    """
    random_secret = secrets.token_hex(24)
    raw_token = f"ss_tok_v1_{random_secret}"
    
    # Compute HMAC-SHA256
    token_hash = hmac.new(
        settings.HMAC_SECRET.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return raw_token, token_hash


def verify_device_token(raw_token: str, expected_hash: str) -> bool:
    """
    Validates a raw bearer token against the stored HMAC hash using constant-time comparison.
    """
    if not raw_token or not expected_hash:
        return False
        
    computed_hash = hmac.new(
        settings.HMAC_SECRET.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_hash, expected_hash)
