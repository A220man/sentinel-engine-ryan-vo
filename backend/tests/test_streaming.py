import pytest
import inspect
from fastapi import FastAPI
from app.main import app
from app.api.routes import api_router


@pytest.mark.asyncio
async def test_streaming_keepalive_source_has_openai_format():
    """Test that streaming endpoint source contains OpenAI-style :keepalive comment."""
    # Find the streaming route
    stream_route = None
    for route in api_router.routes:
        if hasattr(route, 'path') and route.path == "/v1/chat/completions/stream":
            stream_route = route
            break

    assert stream_route is not None, "Streaming route not found"

    # Verify the stream_generator function has keepalive logic
    src = inspect.getsource(stream_route.endpoint)
    assert "keepalive" in src, "Stream generator should contain keepalive logic"
    assert ": keepalive" in src, "Should have OpenAI-style keepalive comment"
    assert "event: ping" in src, "Should have Anthropic-style event ping"
    assert "stream_keepalive_ms" in src, "Should reference stream_keepalive_ms"

    print("Streaming keepalive OpenAI format verified in source")


@pytest.mark.asyncio
async def test_streaming_keepalive_source_has_anthropic_format():
    """Test that streaming endpoint source contains Anthropic-style event: ping frames."""
    # Find the streaming route
    stream_route = None
    for route in api_router.routes:
        if hasattr(route, 'path') and route.path == "/v1/chat/completions/stream":
            stream_route = route
            break

    assert stream_route is not None, "Streaming route not found"

    # Verify the stream_generator function has keepalive logic
    src = inspect.getsource(stream_route.endpoint)
    assert "event: ping" in src, "Should have Anthropic event: ping"
    assert "data: {}" in src or 'data: "{}"' in src, "Should have data field in ping"
    assert "keepalive_interval" in src or "stream_keepalive_ms" in src, "Should use configurable interval"

    print("Streaming keepalive Anthropic format verified in source")
