# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

core-skeleton

## Roadmap

### core-skeleton — Core FastAPI/React skeleton with model listing and chat

Status: done

Acceptance:
- FastAPI backend starts and serves /v1/models endpoint
- React frontend builds and loads
- Frontend can list available models from backend
- Frontend can send chat completion request and receive response
- SQLite persistence for models and API keys
- Docker compose for local development

Implementation: `backend/app/main.py`, `backend/app/api/routes.py`, `backend/app/services/router.py`, `backend/app/models/schema.py`, `backend/requirements.txt`, `frontend/package.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `docker-compose.yaml`, `README.md`

Tests: `backend/tests/test_routes.py`, `backend/tests/test_router.py`, `frontend/src/App.test.tsx`

### smart-routing — Smart routing with failover and per-key concurrency

Status: planned

Acceptance:
- Router selects healthy keys per platform
- Per-key concurrency limits enforced
- Automatic failover on upstream errors
- Hedged requests (race multiple providers)
- Failure attribution: 429/timeout → provider, 404 → model

Implementation: `backend/app/services/router.py`, `backend/tests/test_router.py`

Tests: `backend/tests/test_router.py`

### model-probing — Proactive per-model probing with capability labels

Status: planned

Acceptance:
- Scheduler runs periodic probes per (platform, model, key)
- Labels: tool_capable, chat_only, unavailable, unknown
- Labels decay over time (staleness threshold)
- Dashboard badges show capability labels
- API exposes labels via /v1/models

Implementation: `backend/app/services/prober.py`, `backend/app/api/routes.py`, `frontend/src/components/ModelList.tsx`, `backend/tests/test_prober.py`

Tests: `backend/tests/test_prober.py`

### streaming-keepalive — SSE keep-alive during reasoning buffering

Status: planned

Acceptance:
- SSE pings emitted during reasoning buffer phase
- Anthropic surface: event: ping frames
- OpenAI surface: : keepalive comment lines
- Configurable interval via STREAM_KEEPALIVE_MS env

Implementation: `backend/app/api/routes.py`, `backend/tests/test_streaming.py`

Tests: `backend/tests/test_streaming.py`

### oidc-auth — OIDC authentication with Keycloak

Status: planned

Acceptance:
- OIDC authorization-code flow with PKCE
- HttpOnly SameSite cookies for session
- CSRF protection on cookie-authenticated writes
- Role-based access: viewer, operator, admin
- Keycloak realm import with SAML broker config
- Demo mode binds localhost only

Implementation: `backend/app/api/routes.py`, `backend/app/core/config.py`, `keycloak/realm-export.json`, `docker-compose.yaml`

Tests: `backend/tests/test_auth.py`

### full-dashboard — Complete dashboard UI with management features

Status: planned

Acceptance:
- Platform/key management UI
- Model browsing with filters
- Chat playground with streaming
- Stats and health monitoring
- Settings and demo mode toggle

Implementation: `frontend/src/components/Sidebar.tsx`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/ModelList.tsx`, `frontend/src/store.ts`

Tests: `frontend/src/App.test.tsx`

