"""
Backend test suite for Smart Spectator.
Tests: auth, pairing codes, rule engine, AI output validation.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.database.session import Base, get_db
from app.core.config import settings

# ─── Test database setup ──────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ─── Auth Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "securepassword123",
        "display_name": "Test User",
        "role": "VIEW_ACCESS",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "VIEW_ACCESS"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "securepassword123",
        "display_name": "User",
        "role": "VIEW_ACCESS",
    }
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "securepassword123",
        "display_name": "Test",
        "role": "CAM_CODER",
    })
    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "securepassword123",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "CAM_CODER"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "bad@example.com",
        "password": "correct123",
        "display_name": "Test",
        "role": "VIEW_ACCESS",
    })
    resp = await client.post("/auth/login", json={
        "email": "bad@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    reg = await client.post("/auth/register", json={
        "email": "me@example.com",
        "password": "password123",
        "display_name": "Me",
        "role": "VIEW_ACCESS",
    })
    token = reg.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


# ─── Health Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── Rule Engine Tests ────────────────────────────────────────────────────────

def test_rule_water_level_triggers():
    from app.services.rules.rule_engine import RuleEngine
    from app.models.models import MonitoringType

    engine = RuleEngine()
    obs = {"state": "WATER_LEVEL_RISING", "measurements": {"water_level_percent": 85}, "confidence": 0.9}
    config = {"threshold": 80}
    result = engine.evaluate(obs, config, MonitoringType.WATER_LEVEL, [])
    assert result.triggered is True


def test_rule_water_level_not_triggered():
    from app.services.rules.rule_engine import RuleEngine
    from app.models.models import MonitoringType

    engine = RuleEngine()
    obs = {"state": "WATER_LEVEL_LOW", "measurements": {"water_level_percent": 45}, "confidence": 0.9}
    config = {"threshold": 80}
    result = engine.evaluate(obs, config, MonitoringType.WATER_LEVEL, [])
    assert result.triggered is False


def test_rule_object_presence():
    from app.services.rules.rule_engine import RuleEngine
    from app.models.models import MonitoringType

    engine = RuleEngine()
    obs = {
        "state": "OBJECT_DETECTED",
        "objects": [{"label": "person", "confidence": 0.9}],
        "measurements": {},
        "confidence": 0.9,
        "change_detected": True,
    }
    config = {"target_object": "person", "expect_present": True}
    result = engine.evaluate(obs, config, MonitoringType.OBJECT_PRESENCE, [])
    assert result.triggered is True


def test_rule_machine_state_change():
    from app.services.rules.rule_engine import RuleEngine
    from app.models.models import MonitoringType

    engine = RuleEngine()
    obs = {"state": "MACHINE_STOPPED", "measurements": {}, "confidence": 0.88, "change_detected": True}
    history = [{"state": "MACHINE_RUNNING", "confidence": 0.92}]
    result = engine.evaluate(obs, {}, MonitoringType.MACHINE_STATE, history)
    assert result.triggered is True


# ─── Security Tests ───────────────────────────────────────────────────────────

def test_jwt_create_validate():
    from app.security.jwt import create_access_token, decode_token
    token = create_access_token("user-123", "VIEW_ACCESS")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "VIEW_ACCESS"
    assert payload["type"] == "access"


def test_jwt_expired():
    from datetime import timedelta
    from jose import jwt, JWTError
    from app.core.config import settings
    import time

    payload = {"sub": "user-1", "role": "VIEW_ACCESS", "type": "access", "exp": 1}  # Unix epoch 1 = expired
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(JWTError):
        from app.security.jwt import decode_token
        decode_token(token)


def test_pairing_code_format():
    from app.api.pairing import generate_pairing_code, format_pairing_code, PAIRING_CODE_LENGTH
    code = generate_pairing_code()
    assert len(code) == PAIRING_CODE_LENGTH
    assert code.isupper()
    formatted = format_pairing_code(code)
    assert "-" in formatted
    assert len(formatted) == PAIRING_CODE_LENGTH + 1


def test_pairing_codes_are_unique():
    from app.api.pairing import generate_pairing_code
    codes = {generate_pairing_code() for _ in range(100)}
    assert len(codes) == 100  # All unique


# ─── AI Output Validation Tests ───────────────────────────────────────────────

def test_ai_result_confidence_clamped():
    from app.services.vision.base import AIResult
    result = AIResult(state="TEST", confidence=1.5)
    d = result.to_dict()
    assert d["confidence"] <= 1.0

    result2 = AIResult(state="TEST", confidence=-0.5)
    d2 = result2.to_dict()
    assert d2["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_mock_provider_analyze():
    from app.services.vision.mock_provider import MockProvider
    from app.services.vision.base import TaskContext
    import numpy as np

    provider = MockProvider()
    ctx = TaskContext(task_title="Test", task_description="Test task")
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = await provider.analyze(image, ctx)

    assert result.state != ""
    assert 0.0 <= result.confidence <= 1.0
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_mock_provider_health():
    from app.services.vision.mock_provider import MockProvider
    provider = MockProvider()
    health = await provider.health_check()
    assert health["status"] == "ok"
    assert health["provider"] == "mock"
