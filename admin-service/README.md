# CreditFlow Admin / Ops Service

Operational visibility layer for the platform: active JWT sessions, per-account
aggregated dashboards, a searchable audit trail, and SuperAdmin controls.

## Responsibilities

- Lists active JWT sessions (`jti` values) per account by reading auth-service's
  Redis instance directly (`auth:session:{jti}` keys) — no per-account index
  exists there, so this scans and filters, acceptable for an ops tool.
- Revokes a session on demand by deleting its `jti` key straight out of Redis —
  this immediately invalidates that token at the Gateway, since auth-service's
  own session check (`session_active`) reads the same key.
- Builds a per-account summary (plan tier, seat/member count, credit balance,
  usage this period) via read-only REST calls to tenant-service, credits-service,
  and usage-service's internal endpoints. No writes — every dependency is
  best-effort: an unreachable service leaves that slice of the summary `null`
  rather than failing the whole request.
- Consumes **every** platform event (binds `#` on the shared `creditflow.events`
  topic exchange) into a Postgres `audit_log` table, building a searchable
  per-account timeline of who did what, when. Publishes nothing of its own.
- RBAC: SuperAdmin (platform-level) can view/search across all accounts;
  everyone else is restricted to their own `account_id`.
- Exposes `GET /api/v1/admin/overview` (audit + live per-service health pings +
  sessions/flags placeholders), `GET/DELETE /api/v1/admin/sessions`,
  `GET /api/v1/admin/accounts/{id}/summary`, and `GET /api/v1/admin/audit` for
  the frontend's admin console.

## Internal endpoints this depends on

This service calls trusted, shared-secret-guarded internal routes added to:

- **auth-service**: `GET /api/v1/auth/internal/users/{user_id}` (already existed).
- **tenant-service**: `GET /api/v1/accounts/internal/{account_id}/summary`
  (plan tier, seat count, member count).
- **credits-service**: `GET /api/v1/credits/internal/{account_id}/balance`.
- **usage-service**: `GET /api/v1/usage/summary?account_id=...` — no new route
  needed here; usage-service's identity verifier accepts the shared internal
  token as a synthetic SuperAdmin, and its existing `/summary` route already
  supports a superadmin passing any `account_id`.

All four require `INTERNAL_SERVICE_TOKEN` to match across every service's `.env`.

## Local setup

1. Copy `.env.example` to `.env`.
2. `INTERNAL_SERVICE_TOKEN` must match the same value configured in auth-service,
   tenant-service, credits-service, and usage-service's `.env` files.
3. `REDIS_URL` must point at the **same Redis instance auth-service uses**
   (default `redis://localhost:6379/0`) — not usage-service's Redis, which is a
   separate logical database (`/3`).
4. Run `alembic upgrade head` to create the `admin` schema and `audit_log` table.

## Run

```powershell
cd C:\Development\CreditFlow\admin-service
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m pip install -e .
python -m uvicorn admin_service.main:app --reload --port 8112
```

The RabbitMQ consumer runs inline inside the API process's lifespan — no
separate worker process is needed.
