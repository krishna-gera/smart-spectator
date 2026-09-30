"""
Smart Spectator - Local Query Engine
Conforms to Section 12 of Phase 10 Specification.
Executes structured queries safely using parameterized SQL.
Rejects arbitrary SQL strings completely.
All user-derived values pass through input validation before reaching SQL.
"""

from typing import Dict, Any, List, Optional
import json
import logging
import re
import sqlite3

from services.hub_backend.query.models import StructuredQuery
from services.hub_backend.database.connection import get_db

logger = logging.getLogger("LocalQueryEngine")

# Regex for safe identifiers: alphanumeric, underscores, hyphens only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

# Regex for ISO-ish datetime strings: YYYY-MM-DDTHH:MM:SS with optional fractional/timezone
_SAFE_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?$"
)

# Allowlisted priority values (case-insensitive match)
_VALID_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

# SQL injection signature patterns — reject any value containing these
_SQL_INJECTION_PATTERNS = re.compile(
    r"('|--|;|/\*|\*/|union\s|select\s|insert\s|update\s|delete\s|drop\s|alter\s|"
    r"exec\s|execute\s|xp_|0x[0-9a-f]+|char\s*\(|concat\s*\()",
    re.IGNORECASE,
)


def _empty_result(query: StructuredQuery, limit: int, offset: int) -> Dict[str, Any]:
    """Return a safe empty result set."""
    return {
        "query": query.to_dict(),
        "total_count": 0,
        "limit": limit,
        "offset": offset,
        "results": [],
    }


def _contains_injection(value: str) -> bool:
    """Check if a string value contains SQL injection patterns."""
    return bool(_SQL_INJECTION_PATTERNS.search(value))


def _is_safe_identifier(value: str) -> bool:
    """Validate that a string is a safe identifier (alphanumeric, underscores, hyphens)."""
    return bool(_SAFE_IDENTIFIER_RE.match(value))


def _is_safe_timestamp(value: str) -> bool:
    """Validate that a string looks like an ISO datetime."""
    return bool(_SAFE_TIMESTAMP_RE.match(value))


class LocalQueryEngine:
    """
    Executes validated StructuredQuery objects against the local SQLite store.
    Enforces strict input validation, parameterization, and safe bounds.
    """

    def _validate_query(self, query: StructuredQuery) -> Optional[str]:
        """
        Validate all user-derived fields in the query.
        Returns None if valid, or an error description string if invalid.
        """
        # Validate event_type: must be a safe identifier (no SQL chars)
        if query.event_type:
            if _contains_injection(query.event_type):
                return f"Rejected event_type: contains forbidden pattern"
            if not _is_safe_identifier(query.event_type):
                return f"Rejected event_type: invalid characters"

        # Validate camera_id: must be a safe identifier
        if query.camera_id:
            if _contains_injection(query.camera_id):
                return f"Rejected camera_id: contains forbidden pattern"
            if not _is_safe_identifier(query.camera_id):
                return f"Rejected camera_id: invalid characters"

        # Validate zone_id: must be a safe identifier
        if query.zone_id:
            if _contains_injection(query.zone_id):
                return f"Rejected zone_id: contains forbidden pattern"
            if not _is_safe_identifier(query.zone_id):
                return f"Rejected zone_id: invalid characters"

        # Validate priority: must be in the allowlist
        if query.priority:
            if query.priority.upper() not in _VALID_PRIORITIES:
                return f"Rejected priority: not in allowlist"

        # Validate timestamps: must match ISO datetime format
        if query.after:
            if _contains_injection(query.after):
                return f"Rejected after: contains forbidden pattern"
            if not _is_safe_timestamp(query.after):
                return f"Rejected after: invalid timestamp format"

        if query.before:
            if _contains_injection(query.before):
                return f"Rejected before: contains forbidden pattern"
            if not _is_safe_timestamp(query.before):
                return f"Rejected before: invalid timestamp format"

        # Validate limit and offset bounds
        if not isinstance(query.limit, int) or query.limit < 0:
            return f"Rejected limit: must be a non-negative integer"
        if not isinstance(query.offset, int) or query.offset < 0:
            return f"Rejected offset: must be a non-negative integer"

        return None

    def execute(self, query: StructuredQuery) -> Dict[str, Any]:
        limit = max(1, min(200, query.limit))
        offset = max(0, query.offset)

        # Validate all fields before any SQL construction
        validation_error = self._validate_query(query)
        if validation_error:
            logger.warning("Query rejected by input validation: %s", validation_error)
            return _empty_result(query, limit, offset)

        try:
            if query.is_anomaly:
                return self._execute_anomaly_query(query, limit, offset)
            else:
                return self._execute_event_query(query, limit, offset)
        except sqlite3.OperationalError as e:
            # Defense-in-depth: handle missing tables or schema issues gracefully
            logger.warning("Query execution failed (OperationalError): %s", e)
            return _empty_result(query, limit, offset)
        except sqlite3.DatabaseError as e:
            logger.warning("Query execution failed (DatabaseError): %s", e)
            return _empty_result(query, limit, offset)

    def _execute_event_query(self, query: StructuredQuery, limit: int, offset: int) -> Dict[str, Any]:
        sql = "SELECT * FROM events WHERE 1=1"
        count_sql = "SELECT COUNT(*) FROM events WHERE 1=1"
        params: List[Any] = []

        if query.event_type:
            sql += " AND LOWER(event_type) = LOWER(?)"
            count_sql += " AND LOWER(event_type) = LOWER(?)"
            params.append(query.event_type)

        if query.camera_id:
            sql += " AND camera_id = ?"
            count_sql += " AND camera_id = ?"
            params.append(query.camera_id)

        if query.zone_id:
            sql += " AND zone_id = ?"
            count_sql += " AND zone_id = ?"
            params.append(query.zone_id)

        if query.priority:
            sql += " AND UPPER(priority) = UPPER(?)"
            count_sql += " AND UPPER(priority) = UPPER(?)"
            params.append(query.priority)

        if query.after:
            sql += " AND timestamp >= ?"
            count_sql += " AND timestamp >= ?"
            params.append(query.after)

        if query.before:
            sql += " AND timestamp <= ?"
            count_sql += " AND timestamp <= ?"
            params.append(query.before)

        if query.has_recording is not None:
            if query.has_recording:
                sql += " AND recording_id IS NOT NULL"
                count_sql += " AND recording_id IS NOT NULL"
            else:
                sql += " AND recording_id IS NULL"
                count_sql += " AND recording_id IS NULL"

        with get_db() as conn:
            # Count total matching
            cursor = conn.execute(count_sql, tuple(params))
            row = cursor.fetchone()
            total_count = 0
            if row:
                total_count = row[0] if isinstance(row, tuple) else list(row.values())[0]

            # Fetch page
            sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            page_params = list(params) + [limit, offset]
            cursor = conn.execute(sql, tuple(page_params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]

            records = []
            for row in rows:
                d = dict(zip(cols, row)) if not isinstance(row, dict) else row
                if "details_json" in d and isinstance(d["details_json"], str):
                    try:
                        d["details"] = json.loads(d["details_json"])
                    except Exception:
                        d["details"] = {}
                records.append(d)

            return {
                "query": query.to_dict(),
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "results": records,
            }

    def _execute_anomaly_query(self, query: StructuredQuery, limit: int, offset: int) -> Dict[str, Any]:
        sql = "SELECT * FROM anomalies WHERE 1=1"
        count_sql = "SELECT COUNT(*) FROM anomalies WHERE 1=1"
        params: List[Any] = []

        if query.camera_id:
            sql += " AND camera_id = ?"
            count_sql += " AND camera_id = ?"
            params.append(query.camera_id)

        if query.after:
            sql += " AND timestamp >= ?"
            count_sql += " AND timestamp >= ?"
            params.append(query.after)

        with get_db() as conn:
            cursor = conn.execute(count_sql, tuple(params))
            row = cursor.fetchone()
            total_count = 0
            if row:
                total_count = row[0] if isinstance(row, tuple) else list(row.values())[0]

            sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            page_params = list(params) + [limit, offset]
            cursor = conn.execute(sql, tuple(page_params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]

            records = []
            for row in rows:
                d = dict(zip(cols, row)) if not isinstance(row, dict) else row
                records.append(d)

            return {
                "query": query.to_dict(),
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "results": records,
            }


local_query_engine = LocalQueryEngine()
