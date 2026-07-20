# CreditFlow Auth Service

The service provides transactional signup/login, Argon2 password hashing, RS256 access and rotating
refresh tokens, Redis-backed active-session revocation and failed-login limiting, secure email
verification and password-reset tokens, and RabbitMQ notification events.

## Local setup

```powershell
Copy-Item .env.example ..\.env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn auth_service.main:app --reload --port 8001
```

The existing PostgreSQL database must be named `creditflow`. The migration creates and owns only the
`auth` schema and its `users`, `credentials`, `refresh_tokens`, `password_reset_tokens`, and
`email_verification_tokens` tables.

Operational endpoints are `/health`, `/ready`, `/version`, `/docs`, and `/openapi.json`.

Authentication endpoints are:

- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/switch-account`
- `GET /api/v1/auth/admin/users` (SuperAdmin)
- `PATCH /api/v1/auth/admin/users/{user_id}/platform-role` (SuperAdmin)

## RBAC

`Owner`, `Admin`, and `Member` are account-scoped roles. `SuperAdmin` is a separate global platform
role and bypasses account authorization. Access and refresh JWTs contain `user_id`, `account_id`,
`role`, `account_role`, `platform_role`, `jti`, `iat`, `exp`, issuer, audience, and token type. Set
`BOOTSTRAP_SUPERADMIN_EMAIL` before the initial privileged signup; later global-role changes use the
SuperAdmin API and revoke that user's active sessions. Account switching is validated against Tenant
Service through `TENANT_SERVICE_URL` and returns a newly scoped token pair.

Set `JWT_PRIVATE_KEY_PATH` and `JWT_PUBLIC_KEY_PATH` to developer-provided PEM files before using login
or refresh. Keys are never committed by this service. Redis and RabbitMQ must be reachable through
`REDIS_URL` and `RABBITMQ_URL`; the Auth Service and API Gateway must use the same Redis instance so
the gateway can enforce immediate session revocation.
