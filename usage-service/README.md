# CreditFlow Usage / Metering Service

Owns real-time token quota checks and the durable, append-only AI usage ledger.

## API

- `POST /api/v1/usage/quota/check` reserves estimated tokens before generation.
- `GET /api/v1/usage/summary` returns monthly totals, cost, daily usage, and model breakdown.
- `GET /api/v1/usage/ledger` returns the authenticated account's usage history.
- `GET /health`, `GET /ready`, and `GET /version` expose operational status.

SuperAdmins may supply `account_id` to the summary and ledger endpoints. Other roles are restricted to the account in their JWT.

## Events

- Consumes `ai.generation_completed` from the `ai_events` topic exchange.
- Publishes `usage.threshold_reached` to the `usage_events` topic exchange at 80% and 100%.

## Local setup

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn usage_service.main:app --reload --port 8005
```
