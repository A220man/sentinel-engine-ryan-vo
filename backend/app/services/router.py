from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import httpx
import random
import time
from enum import Enum

from app.models.schema import Platform, ApiKey, Model, RequestLog, RateLimitCooldown
from app.models.database import get_db
from app.services.encryption import encryption_service
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload


class FailureCategory(str, Enum):
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    PROVIDER_ERROR = "provider_error"
    MODEL_NOT_FOUND = "model_not_found"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TIMEOUT = "timeout"
    CLIENT_DISCONNECT = "client_disconnect"
    UNKNOWN = "unknown"


@dataclass
class RouteCandidate:
    platform: Platform
    api_key: ApiKey
    model: Model
    priority: int = 0


@dataclass
class RouteResult:
    success: bool
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    failure_category: Optional[FailureCategory] = None
    latency_ms: int = 0
    tokens: Dict[str, int] = None
    candidate: Optional[RouteCandidate] = None
    hedged: bool = False


class RateLimiter:
    def __init__(self):
        self._key_semaphores: Dict[int, asyncio.Semaphore] = {}
        self._platform_defaults: Dict[str, int] = {
            "openai": 10,
            "anthropic": 5,
            "gemini": 10,
            "ollama": 20,
            "openrouter": 10,
            "groq": 20,
            "together": 10,
            "default": settings.max_concurrent_per_key,
        }

    def get_semaphore(self, key_id: int, limit: Optional[int]) -> asyncio.Semaphore:
        if key_id not in self._key_semaphores:
            effective_limit = limit or self._platform_defaults.get("default", 10)
            self._key_semaphores[key_id] = asyncio.Semaphore(effective_limit)
        return self._key_semaphores[key_id]

    async def acquire(self, key_id: int, limit: Optional[int]) -> bool:
        sem = self.get_semaphore(key_id, limit)
        return await sem.acquire()

    def release(self, key_id: int):
        if key_id in self._key_semaphores:
            self._key_semaphores[key_id].release()

    def get_platform_default(self, platform_name: str) -> int:
        return self._platform_defaults.get(platform_name.lower(), self._platform_defaults["default"])


rate_limiter = RateLimiter()


class Router:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(settings.default_timeout_sec))
        self._cooldown_cache: Dict[str, datetime] = {}

    async def close(self):
        await self.client.aclose()

    async def get_healthy_keys_for_model(
        self, db: AsyncSession, model_id: str, platform_name: Optional[str] = None
    ) -> List[RouteCandidate]:
        """Get all healthy keys that can serve the requested model."""
        query = (
            select(ApiKey)
            .join(Platform)
            .join(Model, and_(Model.platform_id == Platform.id, Model.api_key_id == ApiKey.id))
            .where(Model.model_id == model_id)
            .where(Model.enabled == True)
            .where(ApiKey.enabled == True)
            .where(Platform.enabled == True)
            .options(selectinload(ApiKey.platform), selectinload(ApiKey.models))
        )
        if platform_name:
            query = query.where(Platform.name == platform_name)

        result = await db.execute(query)
        keys = result.scalars().all()

        candidates = []
        for key in keys:
            if await self._is_key_usable(db, key):
                candidates.append(RouteCandidate(
                    platform=key.platform,
                    api_key=key,
                    model=next(m for m in key.models if m.model_id == model_id),
                    priority=key.success_count - key.error_count * 2
                ))

        # Sort by priority (success rate) and add some randomization for exploration
        candidates.sort(key=lambda c: (c.priority, random.random()), reverse=True)
        return candidates

    async def _is_key_usable(self, db: AsyncSession, key: ApiKey) -> bool:
        # Check cooldown
        if key.cooldown_until and key.cooldown_until > datetime.utcnow():
            return False

        # Check quota
        if key.quota_limit is not None and key.quota_remaining is not None:
            if key.quota_remaining <= 0:
                return False

        # Check concurrency
        limit = key.concurrency_limit or rate_limiter.get_platform_default(key.platform.name)
        current = key.current_concurrency or 0
        if current >= limit:
            return False

        # Check rate limit cooldowns
        cooldown_query = select(RateLimitCooldown).where(
            and_(
                RateLimitCooldown.platform == key.platform.name,
                RateLimitCooldown.api_key_id == key.id,
                RateLimitCooldown.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(cooldown_query)
        if result.scalars().first():
            return False

        # Check key status
        if key.status == "unhealthy":
            return False

        return True

    async def classify_failure(self, response: Optional[httpx.Response], error: Optional[Exception]) -> FailureCategory:
        if error:
            if isinstance(error, httpx.TimeoutException):
                return FailureCategory.TIMEOUT
            if isinstance(error, httpx.ConnectError):
                return FailureCategory.PROVIDER_ERROR
            return FailureCategory.UNKNOWN

        if not response:
            return FailureCategory.UNKNOWN

        status = response.status_code
        if status == 429:
            return FailureCategory.PROVIDER_RATE_LIMIT
        if status in (404, 410):
            return FailureCategory.MODEL_NOT_FOUND
        if status == 402 or (status == 403 and "quota" in response.text.lower()):
            return FailureCategory.QUOTA_EXHAUSTED
        if 500 <= status < 600:
            return FailureCategory.PROVIDER_ERROR
        return FailureCategory.UNKNOWN

    async def record_request(
        self,
        db: AsyncSession,
        candidate: RouteCandidate,
        status: str,
        failure_category: Optional[FailureCategory],
        latency_ms: int,
        tokens: Dict[str, int],
        error_message: Optional[str] = None,
        attempt: int = 1,
        hedged: bool = False
    ):
        log = RequestLog(
            request_id=f"req-{int(time.time() * 1000)}-{random.randint(1000, 9999)}",
            model_id=candidate.model.model_id,
            platform=candidate.platform.name,
            api_key_id=candidate.api_key.id,
            status=status,
            failure_category=failure_category.value if failure_category else None,
            latency_ms=latency_ms,
            prompt_tokens=tokens.get("prompt", 0),
            completion_tokens=tokens.get("completion", 0),
            total_tokens=tokens.get("total", 0),
            error_message=error_message,
            attempt_number=attempt,
            hedged=hedged
        )
        db.add(log)

        # Update key stats
        if status == "success":
            candidate.api_key.success_count += 1
            candidate.api_key.error_count = max(0, candidate.api_key.error_count - 1)
        else:
            candidate.api_key.error_count += 1
            if candidate.api_key.error_count >= 5 and candidate.api_key.success_count == 0:
                candidate.api_key.status = "unhealthy"
                candidate.api_key.cooldown_until = datetime.utcnow() + timedelta(minutes=10)

        # Handle rate limit cooldown
        if failure_category == FailureCategory.PROVIDER_RATE_LIMIT:
            cooldown = RateLimitCooldown(
                platform=candidate.platform.name,
                model_id=candidate.model.model_id,
                api_key_id=candidate.api_key.id,
                source="explicit_429",
                reason="HTTP 429 from provider",
                expires_at=datetime.utcnow() + timedelta(minutes=5)
            )
            db.add(cooldown)

        await db.commit()

    async def execute_request(
        self,
        db: AsyncSession,
        candidate: RouteCandidate,
        payload: Dict[str, Any],
        stream: bool = False
    ) -> RouteResult:
        start = time.perf_counter()
        key_plain = encryption_service.decrypt(candidate.api_key.key_encrypted)

        headers = {
            "Authorization": f"Bearer {key_plain}",
            "Content-Type": "application/json",
        }

        # Platform-specific adjustments
        url = candidate.platform.chat_url or f"{candidate.platform.base_url}/chat/completions"
        model_name = candidate.model.model_id

        request_payload = {**payload, "model": model_name}

        try:
            if stream:
                # For streaming, we return the response object directly
                response = await self.client.post(url, json=request_payload, headers=headers, timeout=300)
                latency = int((time.perf_counter() - start) * 1000)
                if response.status_code == 200:
                    return RouteResult(
                        success=True,
                        response=response,
                        latency_ms=latency,
                        tokens={"total": 0},
                        candidate=candidate
                    )
                else:
                    category = await self.classify_failure(response, None)
                    return RouteResult(
                        success=False,
                        error=response.text,
                        failure_category=category,
                        latency_ms=latency,
                        tokens={"total": 0},
                        candidate=candidate
                    )
            else:
                response = await self.client.post(url, json=request_payload, headers=headers)
                latency = int((time.perf_counter() - start) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    return RouteResult(
                        success=True,
                        response=data,
                        latency_ms=latency,
                        tokens={
                            "prompt": usage.get("prompt_tokens", 0),
                            "completion": usage.get("completion_tokens", 0),
                            "total": usage.get("total_tokens", 0)
                        },
                        candidate=candidate
                    )
                else:
                    category = await self.classify_failure(response, None)
                    return RouteResult(
                        success=False,
                        error=response.text,
                        failure_category=category,
                        latency_ms=latency,
                        tokens={"total": 0},
                        candidate=candidate
                    )

        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            category = await self.classify_failure(None, e)
            return RouteResult(
                success=False,
                error=str(e),
                failure_category=category,
                latency_ms=latency,
                tokens={"total": 0},
                candidate=candidate
            )

    async def route_chat_completion(
        self,
        db: AsyncSession,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> RouteResult:
        """Route a chat completion with automatic failover."""

        # If model is "auto", pick the best available
        if model == "auto":
            candidates = await self._get_all_candidates(db, tools is not None)
        else:
            candidates = await self.get_healthy_keys_for_model(db, model)

        if not candidates:
            return RouteResult(
                success=False,
                error="No healthy providers available for model",
                failure_category=FailureCategory.PROVIDER_ERROR
            )

        # Try candidates with optional hedging
        return await self._try_candidates_with_hedge(db, candidates, {
            "messages": messages,
            "tools": tools,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }, stream)

    async def _get_all_candidates(self, db: AsyncSession, needs_tools: bool) -> List[RouteCandidate]:
        query = (
            select(Model)
            .join(Platform)
            .join(ApiKey, Model.api_key_id == ApiKey.id, isouter=True)
            .where(Model.enabled == True)
            .where(Platform.enabled == True)
            .options(selectinload(Model.platform), selectinload(Model.api_key))
        )
        if needs_tools:
            query = query.where(
                or_(
                    Model.capability == "tool_capable",
                    Model.capability == "unknown"
                )
            )

        result = await db.execute(query)
        models = result.scalars().all()

        candidates = []
        for model in models:
            if model.api_key and await self._is_key_usable(db, model.api_key):
                candidates.append(RouteCandidate(
                    platform=model.platform,
                    api_key=model.api_key,
                    model=model,
                    priority=model.api_key.success_count - model.api_key.error_count * 2
                ))

        candidates.sort(key=lambda c: (c.priority, random.random()), reverse=True)
        return candidates

    async def _try_candidates_with_hedge(
        self,
        db: AsyncSession,
        candidates: List[RouteCandidate],
        payload: Dict[str, Any],
        stream: bool
    ) -> RouteResult:
        if not candidates:
            return RouteResult(success=False, error="No candidates", failure_category=FailureCategory.PROVIDER_ERROR)

        # First candidate
        first = candidates[0]
        await rate_limiter.acquire(first.api_key.id, first.api_key.concurrency_limit)
        first.api_key.current_concurrency += 1

        try:
            # Start first request
            task = asyncio.create_task(self.execute_request(db, first, payload, stream))

            # Check if we should hedge
            hedge_delay = settings.hedge_after_ms / 1000.0
            if len(candidates) > 1 and hedge_delay > 0 and not stream:
                await asyncio.sleep(hedge_delay)
                if not task.done():
                    # Start hedged request
                    second = candidates[1]
                    await rate_limiter.acquire(second.api_key.id, second.api_key.concurrency_limit)
                    second.api_key.current_concurrency += 1

                    hedged_task = asyncio.create_task(self.execute_request(db, second, payload, stream))

                    # Wait for first to complete or hedged to win
                    done, pending = await asyncio.wait([task, hedged_task], return_when=asyncio.FIRST_COMPLETED)

                    for p in pending:
                        p.cancel()
                        try:
                            await p
                        except asyncio.CancelledError:
                            pass

                    result = done.pop().result()
                    result.hedged = True

                    # Release second key concurrency
                    rate_limiter.release(second.api_key.id)
                    second.api_key.current_concurrency = max(0, second.api_key.current_concurrency - 1)
                else:
                    result = task.result()
            else:
                result = await task

            # Record result
            await self.record_request(
                db, result.candidate,
                "success" if result.success else "error",
                result.failure_category,
                result.latency_ms,
                result.tokens or {"total": 0},
                result.error,
                hedged=result.hedged
            )

            return result

        finally:
            rate_limiter.release(first.api_key.id)
            first.api_key.current_concurrency = max(0, first.api_key.current_concurrency - 1)


router = Router()