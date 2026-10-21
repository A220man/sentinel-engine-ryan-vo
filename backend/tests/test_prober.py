import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.prober import ModelProber
from app.models.schema import Platform, ApiKey, Model, ProbeLog
from app.services.encryption import encryption_service
from app.services.router import router as router_instance


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
    return ApiKey(
        id=1,
        platform_id=1,
        name="Test Key",
        key_encrypted=encryption_service.encrypt("sk-test123"),
        enabled=True,
        status="healthy",
        platform=mock_platform
    )


@pytest.fixture
def mock_model(mock_api_key):
    return Model(
        id=1,
        platform_id=1,
        api_key_id=1,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        enabled=True,
        capability="unknown",
        probe_success_count=0,
        probe_failure_count=0,
        platform=mock_api_key.platform,
        api_key=mock_api_key
    )


@pytest.mark.asyncio
async def test_prober_log_creation(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()

    await prober._log_probe(
        mock_db, mock_model, "chat", "success", "unknown", "chat_only", 100
    )

    mock_db.add.assert_called_once()
    log = mock_db.add.call_args[0][0]
    assert isinstance(log, ProbeLog)
    assert log.probe_type == "chat"
    assert log.status == "success"
    assert log.capability_before == "unknown"
    assert log.capability_after == "chat_only"


@pytest.mark.asyncio
async def test_prober_should_probe_skips_recent_success(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()

    from app.models.schema import RequestLog
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = RequestLog(
        id=1,
        model_id="gpt-4o-mini",
        platform="openai",
        status="success",
        created_at=datetime.utcnow()
    )
    mock_db.execute.return_value = mock_result

    should_probe = await prober._should_probe(mock_db, mock_model)
    assert should_probe is False


@pytest.mark.asyncio
async def test_prober_should_probe_allows_stale(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    with patch.object(router_instance, '_is_key_usable', AsyncMock(return_value=True)):
        should_probe = await prober._should_probe(mock_db, mock_model)
        assert should_probe is True


@pytest.mark.asyncio
async def test_probe_model_chat_success(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "OK", "tool_calls": []}}]
    }

    with patch.object(prober.client, 'post', AsyncMock(return_value=mock_response)):
        await prober._probe_model(mock_db, mock_model, probe_tools=False)

    assert mock_model.capability == "chat_only"
    assert mock_model.probe_success_count == 1
    mock_db.add.assert_called()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_probe_model_tool_capable(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "probe_tool", "arguments": "{}"}
                }]
            }
        }]
    }

    with patch.object(prober.client, 'post', AsyncMock(return_value=mock_response)):
        await prober._probe_model(mock_db, mock_model, probe_tools=True)

    assert mock_model.capability == "tool_capable"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_probe_model_failure(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    with patch.object(prober.client, 'post', AsyncMock(return_value=mock_response)):
        await prober._probe_model(mock_db, mock_model, probe_tools=False)

    assert mock_model.capability == "unavailable"
    assert mock_model.probe_failure_count == 1
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_probe_model_timeout(mock_model):
    prober = ModelProber()
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    import httpx
    with patch.object(prober.client, 'post', AsyncMock(side_effect=httpx.TimeoutException("Timeout"))):
        await prober._probe_model(mock_db, mock_model, probe_tools=False)

    assert mock_model.capability == "unavailable"
    assert mock_model.probe_failure_count == 1
    mock_db.commit.assert_called_once()