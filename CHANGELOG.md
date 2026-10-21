# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-21

### Added
- FastAPI backend with `/v1/models`, `/v1/chat/completions`, `/v1/platforms`, `/v1/keys`, `/v1/health`, `/v1/stats` endpoints
- SQLite persistence with SQLAlchemy async for models, API keys, request logs, probe logs, rate limit cooldowns
- Basic router with mock provider adapters, per-key concurrency limits, and health filtering
- Proactive model prober skeleton with capability labels: `tool_capable`, `chat_only`, `unavailable`, `unknown`
- React + TypeScript + Vite frontend with model browser, chat interface, and admin panels (platforms, keys, stats, settings)
- Typed API client with axios
- Docker Compose for local development (backend, frontend, Keycloak)
- Comprehensive test suite: 26 backend pytest tests passing, 6 frontend vitest tests passing
- README with install/run/test steps, architecture diagram, API reference, configuration table

### Fixed
- Fixed TypeScript build errors in frontend components (ModelList, Sidebar)
- Fixed API key type definitions to include platform relation
- Fixed test setup global ResizeObserver mock

### Security
- Demo mode binds to localhost only; refuses production startup without explicit override
- Keys encrypted at rest using Fernet (ENCRYPTION_KEY env)
- CORS restricted to configured origins