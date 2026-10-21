import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import httpx

from app.services.router import Router, RouteCandidate, FailureCategory, rate_limiter
from app.services.encryption import encryption_service
from app.models.schema import Platform, ApiKey, Model, RateLimitCooldown


@pytest.fixture
def mock_platform():
    return Platform(
        id=1,
        name="openai",
        display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        chat_url="https://api.openai.com/v1/chat/completions",
        adapter_type="openai-compatible",
        enabled=True
    )


@pytest.fixture
def mock_api_key(mock_platform):
    key = ApiKey(
        id=1,
        platform_id=1,
        name="Test Key",
        key_encrypted=encryption_service.encrypt("sk-test123"),
        enabled=True,
        status="healthy",
        concurrency_limit=10,
        current_concurrency=0,
        platform=mock_platform
    )
    return key


@pytest.fixture
def mock_model(mock_api_key):
    return Model(
        id=1,
        platform_id=1,
        api_key_id=1,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        enabled=True,
        capability="tool_capable",
        platform=mock_api_key.platform,
        api_key=mock_api_key
    )


@pytest.mark.asyncio
async def test_rate_limiter_acquire_release():
    acquired = await rate_limiter.acquire(1, 5)
    assert acquired is True

    acquired2 = await rate_limiter.acquire(1, 5)
    assert acquired2 is True

    rate_limiter.release(1)
    rate_limiter.release(1)


@pytest.mark.asyncio
async def test_classify_failure_429():
    router = Router()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"

    category = await router.classify_failure(mock_response, None)
    assert category == FailureCategory.PROVIDER_RATE_LIMIT


@pytest.mark.asyncio
async def test_classify_failure_404():
    router = Router()
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    category = await router.classify_failure(mock_response, None)
    assert category == FailureCategory.MODEL_NOT_FOUND


@pytest.mark.asyncio
async def test_classify_failure_timeout():
    router = Router()
    category = await router.classify_failure(None, httpx.ReadTimeout("Request timeout"))
    assert category == FailureCategory.TIMEOUT


@pytest.mark.asyncio
async def test_classify_failure_connect_error():
    router = Router()
    category = await router.classify_failure(None, httpx.ConnectError("Connection failed"))
    assert category == FailureCategory.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_classify_failure_500():
    router = Router()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    category = await router.classify_failure(mock_response, None)
    assert category == FailureCategory.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_classify_failure_quota():
    router = Router()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Quota exhausted"

    category = await router.classify_failure(mock_response, None)
    assert category == FailureCategory.QUOTA_EXHAUSTED


@pytest.mark.asyncio
async def test_route_candidate_priority():
    candidate = RouteCandidate(
        platform=Platform(name="openai"),
        api_key=ApiKey(success_count=10, error_count=1),
        model=Model(model_id="gpt-4o"),
        priority=8
    )
    assert candidate.priority == 8


@pytest.mark.asyncio
async def test_router_get_healthy_keys_filters_cooldown(mock_platform, mock_api_key, mock_model):
    router = Router()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    cooldown = RateLimitCooldown(
        platform="openai",
        api_key_id=1,
        source="explicit_429",
        reason="Rate limited",
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = cooldown
    mock_db.execute.return_value = mock_result

    usable = await router._is_key_usable(mock_db, mock_api_key)
    assert usable is False


@pytest.mark.asyncio
async def test_router_get_healthy_keys_filters_unhealthy(mock_api_key):
    router = Router()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first = AsyncMock(return_value=None)
    mock_db.execute.return_value = mock_result

    mock_api_key.status = "unhealthy"

    usable = await router._is_key_usable(mock_db, mock_api_key)
    assert usable is False


@pytest.mark.asyncio
async def test_router_get_healthy_keys_filters_quota(mock_api_key):
    router = Router()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first = AsyncMock(return_value=None)
    mock_db.execute.return_value = mock_result

    mock_api_key.quota_limit = 100
    mock_api_key.quota_remaining = 0

    usable = await router._is_key_usable(mock_db, mock_api_key)
    assert usable is False


@pytest.mark.asyncio
async def test_router_get_healthy_keys_filters_concurrency(mock_api_key):
    router = Router()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first = AsyncMock(return_value=None)
    mock_db.execute.return_value = mock_result

    mock_api_key.concurrency_limit = 2
    mock_api_key.current_concurrency = 2

    usable = await router._is_key_usable(mock_db, mock_api_key)
    assert usable is False