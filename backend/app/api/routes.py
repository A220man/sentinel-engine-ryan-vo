from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.database import get_db
from app.models.schema import Platform, ApiKey, Model, RequestLog
from app.services.router import router
from app.services.prober import prober
from app.services.encryption import encryption_service
from app.core.config import settings

api_router = APIRouter(prefix="/v1", tags=["v1"])


class ModelResponse(BaseModel):
    id: str
    object: str = "model"
    owned_by: str
    capability: str
    platform: str
    display_name: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_tools: Optional[bool] = None
    supports_vision: Optional[bool] = None
    supports_streaming: bool = True


class ModelsListResponse(BaseModel):
    object: str = "list"
    data: List[ModelResponse]


@api_router.get("/models", response_model=ModelsListResponse)
async def list_models(
    capability: Optional[str] = Query(None, description="Filter by capability: tool_capable, chat_only, unavailable, unknown"),
    platform: Optional[str] = Query(None, description="Filter by platform name"),
    enabled_only: bool = Query(True, description="Only return enabled models"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Model).options(selectinload(Model.platform), selectinload(Model.api_key))

    if enabled_only:
        query = query.where(Model.enabled == True)
    if capability:
        query = query.where(Model.capability == capability)
    if platform:
        query = query.join(Platform).where(Platform.name == platform)

    result = await db.execute(query)
    models = result.scalars().all()

    return ModelsListResponse(data=[
        ModelResponse(
            id=m.model_id,
            owned_by=m.platform.name,
            capability=m.capability,
            platform=m.platform.name,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            supports_tools=m.supports_tools,
            supports_vision=m.supports_vision,
            supports_streaming=m.supports_streaming,
            last_probed=m.last_probed.isoformat() if m.last_probed else None,
            capability_updated_at=m.capability_updated_at.isoformat() if m.capability_updated_at else None,
        )
        for m in models
    ])


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[str] = "auto"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


@api_router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await router.route_chat_completion(
        db=db,
        model=request.model,
        messages=[m.model_dump(exclude_none=True) for m in request.messages],
        tools=request.tools,
        stream=request.stream,
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens
    )

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "Upstream error")

    return result.response


@api_router.post("/chat/completions/stream")
async def chat_completions_stream(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    import json

    request.stream = True
    result = await router.route_chat_completion(
        db=db,
        model=request.model,
        messages=[m.model_dump(exclude_none=True) for m in request.messages],
        tools=request.tools,
        stream=True,
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens
    )

    if not result.success or not result.response:
        raise HTTPException(status_code=502, detail=result.error or "Upstream error")

    upstream_response = result.response

    async def stream_generator():
        import asyncio
        keepalive_interval = settings.stream_keepalive_ms / 1000.0
        last_keepalive = asyncio.get_event_loop().time()
        async for line in upstream_response.aiter_lines():
            current_time = asyncio.get_event_loop().time()
            if current_time - last_keepalive >= keepalive_interval:
                # OpenAI-style keepalive comment line
                yield ": keepalive\n"
                # Anthropic-style event ping
                yield "event: ping\ndata: {}\n\n"
                last_keepalive = current_time
            if line:
                yield f"{line}\n"
        await upstream_response.aclose()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# Platform/Key management
class PlatformCreate(BaseModel):
    name: str
    display_name: str
    base_url: str
    models_url: Optional[str] = None
    chat_url: Optional[str] = None
    adapter_type: str
    quota_pool_type: str = "per-key"
    default_concurrency: int = 10


class PlatformResponse(BaseModel):
    id: int
    name: str
    display_name: str
    base_url: str
    models_url: Optional[str] = None
    chat_url: Optional[str] = None
    adapter_type: str
    quota_pool_type: str
    default_concurrency: int
    enabled: bool


@api_router.post("/platforms", response_model=PlatformResponse)
async def create_platform(platform: PlatformCreate, db: AsyncSession = Depends(get_db)):
    p = Platform(**platform.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return PlatformResponse(
        id=p.id,
        name=p.name,
        display_name=p.display_name,
        base_url=p.base_url,
        models_url=p.models_url,
        chat_url=p.chat_url,
        adapter_type=p.adapter_type,
        quota_pool_type=p.quota_pool_type,
        default_concurrency=p.default_concurrency,
        enabled=p.enabled
    )


@api_router.get("/platforms", response_model=List[PlatformResponse])
async def list_platforms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Platform))
    return [PlatformResponse.model_validate(p) for p in result.scalars().all()]


class ApiKeyCreate(BaseModel):
    platform_id: int
    name: str
    key: str
    concurrency_limit: Optional[int] = None
    scope: str = "chat"


class ApiKeyResponse(BaseModel):
    id: int
    platform_id: int
    name: str
    enabled: bool
    status: str
    concurrency_limit: Optional[int] = None
    scope: str
    created_at: str


@api_router.post("/keys", response_model=ApiKeyResponse)
async def create_key(key: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    platform = await db.get(Platform, key.platform_id)
    if not platform:
        raise HTTPException(404, "Platform not found")

    encrypted = encryption_service.encrypt(key.key)
    api_key = ApiKey(
        platform_id=key.platform_id,
        name=key.name,
        key_encrypted=encrypted,
        concurrency_limit=key.concurrency_limit or platform.default_concurrency,
        scope=key.scope
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyResponse(
        id=api_key.id,
        platform_id=api_key.platform_id,
        name=api_key.name,
        enabled=api_key.enabled,
        status=api_key.status,
        concurrency_limit=api_key.concurrency_limit,
        scope=api_key.scope,
        created_at=api_key.created_at.isoformat()
    )


@api_router.get("/keys", response_model=List[ApiKeyResponse])
async def list_keys(platform_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    query = select(ApiKey).options(selectinload(ApiKey.platform))
    if platform_id:
        query = query.where(ApiKey.platform_id == platform_id)
    result = await db.execute(query)
    return [
        ApiKeyResponse(
            id=k.id,
            platform_id=k.platform_id,
            name=k.name,
            enabled=k.enabled,
            status=k.status,
            concurrency_limit=k.concurrency_limit,
            scope=k.scope,
            created_at=k.created_at.isoformat()
        )
        for k in result.scalars().all()
    ]


@api_router.delete("/keys/{key_id}")
async def delete_key(key_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import and_
    key = await db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(404, "Key not found")

    # Cascade: disable models that only belong to this key
    from app.models.schema import Model
    model_query = select(Model).where(Model.api_key_id == key_id)
    result = await db.execute(model_query)
    models = result.scalars().all()
    for m in models:
        # Check if model has other keys
        other_keys = select(Model).where(
            and_(Model.model_id == m.model_id, Model.platform_id == m.platform_id, Model.api_key_id != key_id)
        )
        other = await db.execute(other_keys)
        if not other.scalars().first():
            m.enabled = False

    await db.delete(key)
    await db.commit()
    return {"deleted": True}


# Health and stats
@api_router.get("/health")
async def health():
    return {"status": "healthy", "service": "sentinel-engine"}


@api_router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    total_models = await db.execute(select(func.count(Model.id)))
    total_keys = await db.execute(select(func.count(ApiKey.id)))
    total_platforms = await db.execute(select(func.count(Platform.id)))
    recent_requests = await db.execute(
        select(func.count(RequestLog.id)).where(RequestLog.created_at > datetime.now(timezone.utc) - timedelta(hours=24))
    )
    return {
        "models": total_models.scalar(),
        "api_keys": total_keys.scalar(),
        "platforms": total_platforms.scalar(),
        "requests_24h": recent_requests.scalar()
    }




# --- OIDC Authentication Routes ---

@api_router.get("/auth/login")
async def auth_login(request: Request) -> Dict[str, str]:
    """Initiate OIDC login - redirect to Keycloak."""
    import secrets, os
    auth_url = f"{OIDC_ISSUER}/protocol/openid-connect/authorize"
    params = (
        f"?client_id={KEYCLOAK_CLIENT_ID}"
        f"&redirect_uri={os.environ.get('FRONTEND_URL', 'http://localhost:5173')}/auth/callback"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={secrets.token_hex(16)}"
        f"&code_challenge={os.environ.get('PKCE_CHALLENGE', 'challenge')}"
        f"&code_challenge_method=S256"
    )
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url=auth_url + params)
    response.set_cookie(
        key="auth_state",
        value=params.split("state=")[1].split("&")[0],
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"auth_url": auth_url + params}


@api_router.get("/auth/callback")
async def auth_callback(request: Request) -> Dict[str, str]:
    """Handle Keycloak callback - exchange code for token."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("auth_state")

    if not code or not state or not stored_state or state != stored_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid callback parameters - CSRF state mismatch",
        )

    import httpx
    token_url = f"{OIDC_ISSUER}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as async_client:
        token_response = await async_client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "redirect_uri": os.environ.get('FRONTEND_URL', 'http://localhost:5173') + "/auth/callback",
            },
        )
    tokens = token_response.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No ID token")

    payload = jwt.decode(
        id_token,
        options={"verify_signature": False},
        audience=OIDC_AUDIENCE,
    )

    response = RedirectResponse(url="/")
    response.set_cookie(
        key="sentinel_session",
        value=id_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400,
    )
    response.delete_cookie("auth_state")
    return {"redirect": "/"}


@api_router.post("/auth/logout")
async def auth_logout(response: Response) -> Dict[str, str]:
    """Log out - clear the auth cookie."""
    response.delete_cookie("sentinel_session")
    logout_url = f"{OIDC_ISSUER}/protocol/openid-connect/logout"
    logout_url += f"?post_logout_redirect={os.environ.get('FRONTEND_URL', 'http://localhost:5173')}"
    response.headers["HX-Redirect"] = logout_url
    return {"logout_url": logout_url}


@api_router.get("/auth/me")
async def auth_me(request: Request) -> Dict[str, Any]:
    """Return current user info from the auth cookie."""
    token = request.cookies.get("sentinel_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
            audience=OIDC_AUDIENCE,
        )
        return {
            "sub": payload.get("sub", ""),
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "role": payload.get("role", "viewer"),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
# Probing
@api_router.post("/models/{model_id}/probe")
async def probe_model(model_id: int, probe_tools: bool = False, db: AsyncSession = Depends(get_db)):
    from app.services.prober import prober
    result = await prober.probe_model_now(model_id, probe_tools)
    return result
