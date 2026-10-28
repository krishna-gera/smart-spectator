"""
Smart Spectator - Session Token Minting, Verification, and Revocation
Implements HMAC-SHA256 Base64URL tokens with zero third-party dependencies.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..config import settings
from ..database.connection import db_session
from .models import PrincipalType, TokenPayload
from .roles import Role


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(
    sub: str,
    username: str,
    role: Role,
    principal_type: PrincipalType = PrincipalType.USER,
    ttl_minutes: Optional[int] = None
) -> str:
    """
    Creates a signed HMAC-SHA256 session token.
    """
    ttl = ttl_minutes if ttl_minutes is not None else settings.SESSION_TOKEN_TTL_MINUTES
    now = int(time.time())
    exp = now + (ttl * 60)
    jti = f"ss_jti_{uuid.uuid4().hex}"

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": sub,
        "username": username,
        "role": role.value,
        "type": principal_type.value,
        "iat": now,
        "exp": exp,
        "jti": jti,
    }

    hdr_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{hdr_b64}.{payload_b64}".encode("utf-8")

    sig = hmac.new(settings.HMAC_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{hdr_b64}.{payload_b64}.{sig_b64}"


def is_token_revoked(jti: str) -> bool:
    """Checks if token JTI is listed in revoked_tokens table."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT 1 FROM revoked_tokens WHERE token_id = ?",
            (jti,)
        ).fetchone()
        return row is not None


def verify_access_token(raw_token: str) -> Optional[TokenPayload]:
    """
    Verifies token signature, expiration, and revocation status.
    Returns TokenPayload if valid, None otherwise.
    """
    if not raw_token:
        return None

    parts = raw_token.split(".")
    if len(parts) != 3:
        return None

    hdr_b64, payload_b64, sig_b64 = parts

    # 1. Verify HMAC-SHA256 signature
    signing_input = f"{hdr_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(settings.HMAC_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        return None

    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    # 2. Parse payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    # 3. Verify expiration
    now = int(time.time())
    exp = data.get("exp", 0)
    if now > exp:
        return None

    # 4. Check revocation
    jti = data.get("jti")
    if not jti or is_token_revoked(jti):
        return None

    try:
        return TokenPayload(
            sub=data["sub"],
            username=data.get("username", data["sub"]),
            role=Role(data["role"]),
            principal_type=PrincipalType(data.get("type", "user")),
            iat=data.get("iat", now),
            exp=exp,
            jti=jti
        )
    except Exception:
        return None


def revoke_token(raw_token: str) -> bool:
    """Revokes a valid token by inserting its JTI into revoked_tokens."""
    payload = verify_access_token(raw_token)
    if not payload:
        return False

    exp_iso = datetime.fromtimestamp(payload.exp, tz=timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO revoked_tokens (token_id, expires_at, revoked_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (payload.jti, exp_iso)
        )
    return True
