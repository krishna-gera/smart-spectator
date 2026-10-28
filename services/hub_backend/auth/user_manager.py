"""
Smart Spectator - User Management & Authentication Subsystem
Manages operator and admin accounts in SQLite with PBKDF2 hashed credentials.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from ..config import settings
from ..database.connection import db_session
from .models import Principal, PrincipalType
from .roles import Role
from .passwords import hash_password, verify_password


class UserManager:
    """Manages authenticated operators and administrators."""

    def seed_default_admin(self) -> None:
        """
        Seeds default administrator user if users table is empty.
        Uses configured HUB_ADMIN_USERNAME and HUB_ADMIN_PASSWORD.
        """
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
            if row and row["count"] == 0:
                pwd_hash, salt = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
                user_id = f"usr_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, password_hash, salt, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, 'admin', 1, CURRENT_TIMESTAMP)
                    """,
                    (user_id, settings.DEFAULT_ADMIN_USERNAME, pwd_hash, salt)
                )
                print(f"[UserManager] Seeded default administrator user '{settings.DEFAULT_ADMIN_USERNAME}' ({user_id})")

    def authenticate_user(self, username: str, plain_password: str) -> Optional[Principal]:
        """Validates username and password. Returns Principal on success, None on failure."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            ).fetchone()
            if not row:
                return None

            if not verify_password(plain_password, row["password_hash"], row["salt"]):
                return None

            # Update last_login
            conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
                (row["user_id"],)
            )

            return Principal(
                id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                principal_type=PrincipalType.USER,
                is_active=bool(row["is_active"])
            )

    def get_user_by_id(self, user_id: str) -> Optional[Principal]:
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ? AND is_active = 1",
                (user_id,)
            ).fetchone()
            if not row:
                return None
            return Principal(
                id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                principal_type=PrincipalType.USER,
                is_active=bool(row["is_active"])
            )

    def create_user(self, username: str, plain_password: str, role: Role) -> Principal:
        """Creates a new user account. Raises ValueError if username already exists."""
        with db_session() as conn:
            existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                raise ValueError(f"Username '{username}' already exists")

            pwd_hash, salt = hash_password(plain_password)
            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO users (user_id, username, password_hash, salt, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (user_id, username, pwd_hash, salt, role.value)
            )

            return Principal(
                id=user_id,
                username=username,
                role=role,
                principal_type=PrincipalType.USER,
                is_active=True
            )

    def list_users(self) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cur = conn.execute(
                "SELECT user_id, username, role, is_active, created_at, last_login FROM users ORDER BY created_at ASC"
            )
            return cur.fetchall()


user_manager = UserManager()
