# CreditFlow API Gateway

The stateless public entry point for CreditFlow. It validates RS256 access tokens, rate-limits callers with Redis, routes requests to independently deployable services, verifies and deduplicates webhooks, publishes normalized RabbitMQ events, composes dashboard responses, and re-streams AI generation events over SSE. It owns no database.

## Architecture

Requests pass through request/correlation context, trusted-host/CORS/security middleware, authentication, and sliding-window rate limiting before reaching thin route handlers. `ProxyService` is the sole HTTPX downstream boundary. Redis owns rate windows, webhook idempotency, and Pub/Sub. `RabbitPublisher` is publisher-only and uses a durable topic exchange with persistent mandatory messages and publisher confirms.

## Routes

| Route | Access | Purpose |
|---|---|---|
| `/health`, `/version`, `/docs`, `/redoc`, `/openapi.json` | Public | Liveness, metadata, API documentation |
| `/ready` | Public | Redis and RabbitMQ readiness |
| `/api/v1/auth/*` | Login/signup/refresh paths public | Proxied Auth Service traffic |
| `/api/v1/webhooks/{stripe,linkedin,openrouter}` | Signature protected | Verified, deduplicated event ingress |
| `/api/v1/dashboard/overview` | JWT | Concurrent six-service composition with degradation metadata |
| `/api/v1/ai/generations/{id}/stream` | JWT and account ownership | Redis Pub/Sub SSE stream |
| `/api/v1/{service}/...` | JWT unless explicitly public | Downstream REST proxy |

## Security and token flow

Protected requests require an RS256 access JWT with issuer, audience, expiry, token type, user ID, account ID, and account role. Client-supplied trusted identity headers are stripped and replaced from verified claims. Expired tokens return `TOKEN_EXPIRED`; the frontend explicitly calls `/api/v1/auth/refresh`. The gateway never issues or silently refreshes tokens.

## Rate limiting

Redis runs an atomic Lua sliding window keyed by IP for public traffic and account for authenticated traffic. Responses include limit, remaining, and reset headers. A 429 includes `Retry-After`. `ALLOW_IN_MEMORY_REDIS=true` is development/test-only; production readiness fails when Redis is unavailable.

## Webhook and RabbitMQ flow

Stripe uses the official SDK. LinkedIn and OpenRouter use constant-time SHA-256 HMAC verification over the raw body. Verified event IDs are stored with Redis `SET NX` for 24 hours, normalized, then published to the durable `creditflow.events` topic exchange as `billing.*`, `social.*`, or `ai.*`. The envelope contains event ID/type, schema version, UTC occurrence time, source, correlation ID, and payload. A webhook is acknowledged only after confirmed publication.

## SSE flow

The gateway verifies generation ownership through the AI service, subscribes to `ai:stream:{account_id}:{generation_id}`, emits named events and heartbeat frames, stops on completion/failure/disconnect, and always closes the subscription. `SSEService` can later be backed by a direct upstream stream without changing the endpoint.

## Setup and validation

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\ruff.exe format .
.venv\Scripts\ruff.exe check .
.venv\Scripts\mypy.exe src tests
.venv\Scripts\pytest.exe
.venv\Scripts\uvicorn.exe api_gateway.main:app --reload --port 8080
```

Configuration is documented in `.env.example`; local secrets belong only in the root `../.env`. Unit tests use in-memory substitutes and mocked HTTP. Set `RUN_INFRASTRUCTURE_TESTS=true` with live Redis/RabbitMQ URLs for the opt-in container integration check.

```powershell
docker build -t creditflow-api-gateway:local .
docker run --rm -p 8080:8080 --env-file ../.env creditflow-api-gateway:local
```

## RBAC

Every protected request is verified as RS256 and must contain `user_id`, `account_id`, `role`,
`account_role`, `jti`, issuer, audience, expiry, and access-token type. Redis session presence is checked
before routing. Financial Billing routes require Owner, global `/api/v1/admin` routes require
SuperAdmin, and SuperAdmin bypass is explicit. The gateway forwards identity headers derived only from
the verified token; client-supplied identity headers are never trusted.

## Frontend status and assumptions

The frontend retains its MSW business mocks. Only gateway liveness/version is probed through the real port and degrades to a typed unavailable state without affecting the approved UI. Downstream services are intentionally absent; proxy and composition tests mock their contracts. Provider HMAC header is `X-Webhook-Signature` pending provider-specific production agreement.
