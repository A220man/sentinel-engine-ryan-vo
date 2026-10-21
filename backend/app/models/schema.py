from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    base_url = Column(String(512), nullable=True)
    models_url = Column(String(512), nullable=True)
    chat_url = Column(String(512), nullable=True)
    adapter_type = Column(String(32), nullable=False)  # openai-compatible, anthropic, gemini, ollama
    quota_pool_type: str = Column(String(16), default="per-key")  # per-key, per-account
    default_concurrency: int = Column(Integer, default=10)
    enabled: bool = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    keys = relationship("ApiKey", back_populates="platform")
    models = relationship("Model", back_populates="platform")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    name = Column(String(128), nullable=False)
    key_encrypted = Column(Text, nullable=False)
    enabled: bool = Column(Boolean, default=True)
    status: str = Column(String(32), default="unknown")  # healthy, unhealthy, suspect, unknown
    last_checked = Column(DateTime, nullable=True)
    error_count: int = Column(Integer, default=0)
    success_count: int = Column(Integer, default=0)
    quota_remaining: Optional[int] = Column(Integer, nullable=True)
    quota_limit: Optional[int] = Column(Integer, nullable=True)
    quota_reset_at: Optional[datetime] = Column(DateTime, nullable=True)
    concurrency_limit: Optional[int] = Column(Integer, nullable=True)
    current_concurrency: int = Column(Integer, default=0)
    cooldown_until: Optional[datetime] = Column(DateTime, nullable=True)
    scope: str = Column(String(64), default="chat")  # chat, embeddings, all
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    platform = relationship("Platform", back_populates="keys")
    models = relationship("Model", back_populates="api_key")


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    model_id = Column(String(256), nullable=False)  # e.g., "gpt-4o-mini", "claude-3-haiku"
    display_name = Column(String(256), nullable=True)
    enabled: bool = Column(Boolean, default=True)
    capability: str = Column(String(32), default="unknown")  # tool_capable, chat_only, unavailable, unknown
    capability_updated_at: Optional[datetime] = Column(DateTime, nullable=True)
    context_window: Optional[int] = Column(Integer, nullable=True)
    max_output_tokens: Optional[int] = Column(Integer, nullable=True)
    supports_tools: Optional[bool] = Column(Boolean, nullable=True)
    supports_vision: Optional[bool] = Column(Boolean, nullable=True)
    supports_streaming: bool = Column(Boolean, default=True)
    source: str = Column(String(32), default="manual")  # catalog, manual, custom
    last_probed = Column(DateTime, nullable=True)
    probe_success_count: int = Column(Integer, default=0)
    probe_failure_count: int = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    platform = relationship("Platform", back_populates="models")
    api_key = relationship("ApiKey", back_populates="models")

    __table_args__ = (
        UniqueConstraint("platform_id", "model_id", "api_key_id", name="uq_platform_model_key"),
        Index("ix_models_capability", "capability"),
        Index("ix_models_enabled", "enabled"),
    )


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, unique=True)
    model_id = Column(String(256), nullable=True)
    platform = Column(String(64), nullable=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    status: str = Column(String(32), nullable=False)  # success, error, rate_limited, canceled, model_not_found
    failure_category: Optional[str] = Column(String(32), nullable=True)  # provider_rate_limit, provider_error, model_not_found, quota_exhausted, timeout, client_disconnect
    latency_ms: int = Column(Integer, default=0)
    prompt_tokens: int = Column(Integer, default=0)
    completion_tokens: int = Column(Integer, default=0)
    total_tokens: int = Column(Integer, default=0)
    error_message: Optional[str] = Column(Text, nullable=True)
    attempt_number: int = Column(Integer, default=1)
    hedged: bool = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    api_key = relationship("ApiKey")


class ProbeLog(Base):
    __tablename__ = "probe_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    probe_type: str = Column(String(32), nullable=False)  # chat, tool
    status: str = Column(String(32), nullable=False)  # success, failure, timeout
    capability_before: str = Column(String(32), nullable=False)
    capability_after: str = Column(String(32), nullable=False)
    latency_ms: int = Column(Integer, default=0)
    error_message: Optional[str] = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    model = relationship("Model")
    api_key = relationship("ApiKey")


class RateLimitCooldown(Base):
    __tablename__ = "rate_limit_cooldowns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(64), nullable=False)
    model_id = Column(String(256), nullable=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    source: str = Column(String(32), nullable=False)  # heuristic, explicit_429, provider_header
    reason: str = Column(String(256), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cooldown_lookup", "platform", "model_id", "api_key_id", "expires_at"),
    )