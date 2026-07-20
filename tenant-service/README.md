# CreditFlow Tenant Service

The service owns the PostgreSQL `tenant` schema and provides account creation, account membership,
account listing, owner/admin role management, and secure single-use invitations. It verifies Auth-issued
RS256 bearer tokens and consumes `user.registered` through RabbitMQ to create the user's individual
account. The frontend switches workspaces through Auth Service, which validates membership here before
issuing account-scoped tokens.

## Local setup

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn tenant_service.main:app --reload --port 8002
```

The PostgreSQL database must be named `creditflow`. Operational endpoints are `/health`, `/ready`,
`/version`, `/docs`, and `/openapi.json`.

Account endpoints are under `/api/v1/accounts`, and invite acceptance is under `/api/v1/invites`.
Requests use Auth-issued bearer tokens. Persisted `account_members.role` values remain authoritative for
owner/admin access.

RabbitMQ uses the durable `creditflow.events` topic exchange. This service consumes `user.registered` and
publishes `account.created`, `account.updated`, `member.invited`, `member.joined`,
`member.role_updated`, and `member.removed`. Owners manage all account roles; admins may manage members
but cannot alter owners or other admins; members have read-only account access. SuperAdmins bypass
account restrictions. `GET /api/v1/accounts/{account_id}/membership/me` is the trusted account-switch
membership check, while `GET /api/v1/accounts` is SuperAdmin-only global account listing.
