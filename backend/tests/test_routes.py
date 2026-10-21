import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.models.schema import Platform, ApiKey, Model
from app.services.encryption import encryption_service


@pytest.mark.asyncio
async def test_health_endpoint(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_models_empty(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert data["data"] == []


@pytest.mark.asyncio
async def test_create_platform(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/platforms", json={
            "name": "openai",
            "display_name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "adapter_type": "openai-compatible"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "openai"
        assert data["display_name"] == "OpenAI"
        assert data["adapter_type"] == "openai-compatible"


@pytest.mark.asyncio
async def test_create_api_key(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        platform_resp = await client.post("/v1/platforms", json={
            "name": "openai",
            "display_name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "adapter_type": "openai-compatible"
        })
        platform_id = platform_resp.json()["id"]

        response = await client.post("/v1/keys", json={
            "platform_id": platform_id,
            "name": "Test Key",
            "key": "sk-test123",
            "scope": "chat"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Key"
        assert data["platform_id"] == platform_id
        assert data["status"] == "unknown"


@pytest.mark.asyncio
async def test_model_crud_with_key(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        platform_resp = await client.post("/v1/platforms", json={
            "name": "openai",
            "display_name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "adapter_type": "openai-compatible"
        })
        platform_id = platform_resp.json()["id"]

        key_resp = await client.post("/v1/keys", json={
            "platform_id": platform_id,
            "name": "Test Key",
            "key": "sk-test123"
        })
        key_id = key_resp.json()["id"]

        response = await client.get("/v1/models")
        assert response.status_code == 200
        assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_delete_key_cascades_models(test_db, db_session: AsyncSession):
    platform = Platform(
        name="openai",
        display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        adapter_type="openai-compatible"
    )
    db_session.add(platform)
    await db_session.flush()

    encrypted_key = encryption_service.encrypt("sk-test123")
    api_key = ApiKey(
        platform_id=platform.id,
        name="Test Key",
        key_encrypted=encrypted_key
    )
    db_session.add(api_key)
    await db_session.flush()

    model = Model(
        platform_id=platform.id,
        api_key_id=api_key.id,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        enabled=True,
        capability="tool_capable"
    )
    db_session.add(model)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "gpt-4o-mini"

        del_response = await client.delete(f"/v1/keys/{api_key.id}")
        assert del_response.status_code == 200

        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0


@pytest.mark.asyncio
async def test_stats_endpoint(test_db, db_session: AsyncSession):
    platform = Platform(
        name="openai",
        display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        adapter_type="openai-compatible"
    )
    db_session.add(platform)
    await db_session.flush()

    encrypted_key = encryption_service.encrypt("sk-test123")
    api_key = ApiKey(platform_id=platform.id, name="Key1", key_encrypted=encrypted_key)
    db_session.add(api_key)

    model = Model(platform_id=platform.id, api_key_id=api_key.id, model_id="gpt-4o", enabled=True)
    db_session.add(model)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] >= 1
        assert data["api_keys"] >= 1
        assert data["platforms"] >= 1