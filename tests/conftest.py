"""
Smart Spectator - Global Test Configuration and Fixtures
Provides authenticated headers and shared mocks for integration and API tests.
"""

import pytest
from services.hub_backend.auth.tokens import create_access_token
from services.hub_backend.auth.models import Role


@pytest.fixture
def admin_token() -> str:
    return create_access_token("usr_test_admin", "admin", Role.ADMIN)


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def operator_token() -> str:
    return create_access_token("usr_test_operator", "operator", Role.OPERATOR)


@pytest.fixture
def operator_headers(operator_token: str) -> dict:
    return {"Authorization": f"Bearer {operator_token}"}


@pytest.fixture
def viewer_token() -> str:
    return create_access_token("usr_test_viewer", "viewer", Role.VIEWER)


@pytest.fixture
def viewer_headers(viewer_token: str) -> dict:
    return {"Authorization": f"Bearer {viewer_token}"}
