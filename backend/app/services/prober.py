from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import httpx
import random

from app.models.schema import Platform, ApiKey, Model, ProbeLog
from app.models.database import get_db
from app.services.encryption import encryption_service
from app.services.router import router, FailureCategory
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload


class ModelProber:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(settings.probe_timeout_sec))
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def close(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()

    async def start(self):
        if not settings.probe_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._probe_loop())

    async def _probe_loop(self):
        while self._running:
            try:
                await self.probe_all_models()
            except Exception as e:
                print(f"Probe loop error: {e}")
            await asyncio.sleep(settings.probe_interval_sec)

    async def probe_all_models(self):
        async for db in get_db():
            # Get models that need probing (not probed recently, or unknown capability)
            cutoff = datetime.utcnow() - timedelta(seconds=settings.probe_interval_sec * 2)
            query = select(Model).where(
                and_(
                    Model.enabled == True,
                    or_(
                        Model.capability == "unknown",
                        Model.last_probed == None,
                        Model.last_probed < cutoff
                    )
                )
            ).options(selectinload(Model.platform), selectinload(Model.api_key))

            result = await db.execute(query)
            models = result.scalars().all()

            for model in models:
                if model.api_key and await self._should_probe(db, model):
                    await self._probe_model(db, model)

    async def _should_probe(self, db: AsyncSession, model: Model) -> bool:
        # Skip if model had recent real traffic (check request logs)
        from app.models.schema import RequestLog
        recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
        query = select(RequestLog).where(
            and_(
                RequestLog.model_id == model.model_id,
                RequestLog.platform == model.platform.name,
                RequestLog.created_at > recent_cutoff,
                RequestLog.status == "success"
            )
        ).limit(1)
        result = await db.execute(query)
        if result.scalars().first():
            return False  # Recent success, skip probe

        # Check key is usable
        if model.api_key:
            from app.services.router import router as router_instance
            return await router_instance._is_key_usable(db, model.api_key)
        return False

    async def _probe_model(self, db: AsyncSession, model: Model, probe_tools: bool = False):
        if not model.api_key:
            return

        key_plain = encryption_service.decrypt(model.api_key.key_encrypted)
        headers = {
            "Authorization": f"Bearer {key_plain}",
            "Content-Type": "application/json",
        }

        url = model.platform.chat_url or f"{model.platform.base_url}/chat/completions"

        # Probe payload - minimal chat request
        if probe_tools:
            messages = [{"role": "user", "content": "Reply with OK"}]
            tools = [{
                "type": "function",
                "function": {
                    "name": "probe_tool",
                    "description": "Probe tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            }]
            payload = {
                "model": model.model_id,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": 10,
                "temperature": 0
            }
            probe_type = "tool"
        else:
            payload = {
                "model": model.model_id,
                "messages": [{"role": "user", "content": "Reply with OK"}],
                "max_tokens": 10,
                "temperature": 0
            }
            probe_type = "chat"

        capability_before = model.capability
        start = datetime.utcnow()

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

            if response.status_code == 200:
                data = response.json()
                # Check for tool call in response
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls", [])

                if probe_tools and tool_calls:
                    capability_after = "tool_capable"
                elif probe_tools and not tool_calls:
                    capability_after = "chat_only"
                else:
                    # For chat probe, if successful, at least chat_only
                    capability_after = "chat_only" if capability_before == "unknown" else capability_before

                model.capability = capability_after
                model.last_probed = datetime.utcnow()
                model.probe_success_count += 1

                await self._log_probe(db, model, probe_type, "success", capability_before, capability_after, latency_ms)

            else:
                capability_after = "unavailable"
                model.capability = capability_after
                model.last_probed = datetime.utcnow()
                model.probe_failure_count += 1

                await self._log_probe(db, model, probe_type, "failure", capability_before, capability_after, latency_ms, response.text)

        except Exception as e:
            latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            capability_after = "unavailable"
            model.capability = capability_after
            model.last_probed = datetime.utcnow()
            model.probe_failure_count += 1

            await self._log_probe(db, model, probe_type, "timeout", capability_before, capability_after, latency_ms, str(e))

        await db.commit()

    async def _log_probe(
        self,
        db: AsyncSession,
        model: Model,
        probe_type: str,
        status: str,
        cap_before: str,
        cap_after: str,
        latency_ms: int,
        error: Optional[str] = None
    ):
        log = ProbeLog(
            model_id=model.id,
            api_key_id=model.api_key_id,
            probe_type=probe_type,
            status=status,
            capability_before=cap_before,
            capability_after=cap_after,
            latency_ms=latency_ms,
            error_message=error
        )
        db.add(log)

    async def probe_model_now(self, model_id: int, probe_tools: bool = False) -> Dict[str, Any]:
        """Manually trigger a probe for a specific model."""
        async for db in get_db():
            query = select(Model).where(Model.id == model_id).options(selectinload(Model.platform), selectinload(Model.api_key))
            result = await db.execute(query)
            model = result.scalars().first()
            if not model:
                return {"success": False, "error": "Model not found"}
            if not model.api_key:
                return {"success": False, "error": "Model has no API key"}

            await self._probe_model(db, model, probe_tools)
            return {"success": True, "capability": model.capability}


prober = ModelProber()