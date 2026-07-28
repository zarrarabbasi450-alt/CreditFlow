# CreditFlow

CreditFlow is a multi-tenant SaaS platform for AI-assisted content creation: teams generate posts with
streaming AI text/image generation, schedule and publish them to LinkedIn, research supporting material
with a web scraper, and pay for usage through a credit system with a first-party Stripe top-up flow and a
peer-to-peer credit marketplace.

The system is 13 independent backend services behind a single API gateway, communicating over both
synchronous HTTP (service-to-service calls) and asynchronous events (RabbitMQ), plus a Next.js frontend.

## Architecture

```
                     ┌─────────────┐
   Browser  ───────▶ │  Frontend   │  Next.js 15 (App Router), port 3000
                     └──────┬──────┘
                            │ REST (JWT bearer + httpOnly refresh cookie)
                            ▼
                     ┌─────────────┐
                     │ API Gateway │  auth verification, per-route RBAC,
                     │  (:8080)    │  rate limiting, webhook verification, SSE proxy
                     └──────┬──────┘
        ┌───────────────────┼────────────────────────────────────┐
        ▼                   ▼                                    ▼
┌───────────────┐  ┌────────────────┐                   ┌────────────────────┐
│ auth-service   │  │ tenant-service │  ...9 more services, each single-purpose,
│ (:8001)        │  │ (:8002)        │  each with its own database/schema
└───────┬────────┘  └───────┬────────┘  (Postgres schema, or MongoDB for scraper-service)
        │                   │
        └─────────┬─────────┴──────────── RabbitMQ (topic exchanges) ───────────┐
                   ▼                                                            ▼
          domain events (account.created, invoice.paid, ai.generation_completed,
          content.scheduled, content.created, member.invited, ...) consumed by
          whichever services care, each with its own durable queue + DLX
```

### The 13 backend services

| Service | Port | Owns (DB schema) | Responsibility |
|---|---|---|---|
| `api-gateway` | 8080 | — (stateless) | JWT verification, RBAC enforcement, rate limiting, request proxying, SSE relay, Stripe/LinkedIn webhook verification |
| `auth-service` | 8001 | `auth` | Signup/login, password hashing (Argon2), RS256 JWT issuance, email verification, OTP password reset, session revocation |
| `tenant-service` | 8002 | `tenant` | Accounts (Individual/Team), memberships, roles (Owner/Admin/Member), invites |
| `billing-service` | 8003 | `billing` | Stripe subscriptions, invoices, refunds, transactional outbox for event publishing |
| `credits-service` | 8004 | `credits` | Credit ledger/balance, peer-to-peer marketplace listings and purchases |
| `usage-service` | 8005 | `usage` | Token usage metering and quota tracking |
| `ai-generation-service` | 8006 | `ai_generation` | OpenRouter-backed generation, SSE token streaming, credit consumption |
| `content-service` | 8007 | `content` | Content drafts, versioning, approve/publish workflow, auto-drafts from completed generations |
| `scheduler-service` (+ `scheduler-worker`) | 8108 | `scheduler` | Calendar scheduling; Celery beat worker fires due posts |
| `social-publishing-service` | 8109 | `social` | LinkedIn OAuth connect, publishing, per-post delivery status |
| `scraper-service` (+ `scraper-worker`) | 8110 | MongoDB (`creditflow_scraper`) | Web research jobs (URL/SERP/AI research), async worker consumes scrape requests |
| `notification-service` | 8111 | `notifications` | Email (Gmail API or Resend) and Slack delivery for domain events, delivery log |
| `admin-service` | 8112 | `admin` | Platform-wide audit log, active-session viewer, cross-account operational overview (SuperAdmin only) |

Each service that consumes events keeps its own `processed_events` table (or Mongo collection, for the
scraper) keyed on the event's `event_id`, so a redelivered message after a crash/restart is a no-op instead
of double-processing. Every queue is durable, uses `delivery_mode=2` (persistent messages), and is bound to
a dead-letter exchange with a bounded retry count (`x-delivery-limit`) so a poison message can't loop
forever. Billing-service's state changes and their outbound events are written in the same database
transaction (transactional outbox pattern), with a separate poller publishing them to RabbitMQ — so a
crash between "charge the card" and "tell everyone" can't happen.

### Auth model

- Access tokens: short-lived RS256 JWTs, kept in memory only on the frontend (never localStorage).
- Refresh tokens: rotated on every use, delivered to the browser as an httpOnly cookie set by the gateway
  (never readable by frontend JS).
- Roles: `Owner` / `Admin` / `Member` are account-scoped; `SuperAdmin` is a separate global platform role
  that bypasses account checks. The gateway enforces role checks for admin/billing/marketplace-management/
  team-management routes at the edge, on top of each service's own authorization.

## Prerequisites

- Docker Desktop
- A running PostgreSQL instance (native install or your own container) with a database named `creditflow`
- Long-lived Redis, RabbitMQ, and MongoDB instances reachable from Docker containers

This repo's `docker-compose.yml` deliberately does **not** containerize Postgres/Redis/RabbitMQ/MongoDB —
it assumes you already have them running and reaches them via `host.docker.internal`. Bring your own infra
up first:

```bash
# example — adjust to however you already run these
docker start creditflow-redis creditflow-rabbitmq creditflow-mongo
# native Postgres should already be running, with a `creditflow` database created
```

## Setup

1. **Generate the JWT signing keypair** (shared by every backend service, mounted read-only):

   ```bash
   cd keys
   python generate_keys.py   # writes private_key.pem and public_key.pem
   cd ..
   ```

2. **Create a `.env` file at the repo root** with the secrets `docker-compose.yml` reads. At minimum:

   ```bash
   POSTGRES_PASSWORD=...
   INTERNAL_SERVICE_TOKEN=...          # shared secret for trusted service-to-service calls
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PRO_PRICE_ID=price_...
   STRIPE_TEAM_PRICE_ID=price_...
   STRIPE_ENTERPRISE_PRICE_ID=price_...
   OPENROUTER_API_KEY=...              # AI generation
   LINKEDIN_CLIENT_ID=...
   LINKEDIN_CLIENT_SECRET=...
   LINKEDIN_WEBHOOK_SECRET=...
   SOCIAL_TOKEN_ENCRYPTION_KEY=...     # Fernet key for encrypting stored LinkedIn tokens
   SERPAPI_API_KEY=...                 # scraper SERP jobs
   EMAIL_PROVIDER=gmail                # or "resend"
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REFRESH_TOKEN=...
   GMAIL_SENDER_EMAIL=...
   # or, if EMAIL_PROVIDER=resend:
   # RESEND_API_KEY=...
   BOOTSTRAP_SUPERADMIN_EMAIL=you@example.com   # whichever email you'll sign up as your platform admin
   ```

   Every var has a placeholder default in `docker-compose.yml` if omitted, but Stripe/OpenRouter/LinkedIn/
   email features won't work until the real values are supplied. See `docker-compose.yml` for the complete,
   authoritative list (it's the single source of truth for what each service reads).

   > **SuperAdmin bootstrapping:** `auth-service` promotes whichever email matches
   > `BOOTSTRAP_SUPERADMIN_EMAIL` to the `SuperAdmin` platform role automatically at signup. Set it before
   > you sign up your admin account. Every other SuperAdmin promotion after the first goes through
   > `PATCH /api/v1/auth/admin/users/{user_id}/platform-role`, which itself requires an existing SuperAdmin.

3. **Register your LinkedIn OAuth app's redirect URI** (LinkedIn Developer Console → your app → Auth) as:

   ```
   http://localhost:8080/api/v1/publishing/linkedin/callback
   ```

   (It goes through the gateway, not directly to `social-publishing-service`, so the whole app stays behind
   one edge.)

4. **Build and start everything:**

   ```bash
   docker compose up -d --build
   ```

   First boot needs each service's database schema created. Every service ships its own Alembic migrations
   (see its `migrations/` folder); run `alembic upgrade head` from within each service's directory (with
   `DATABASE_URL` pointed at your Postgres instance) before or after the first `docker compose up` — the
   containers don't run migrations automatically on startup.

5. **Verify:**

   ```bash
   curl http://localhost:8080/health
   open http://localhost:3000
   ```

   There's no seed data — sign up a fresh account through the UI or `POST /api/v1/auth/signup`.

## Development

Each service is a standalone Python/FastAPI project with its own `requirements.txt` /
`requirements-dev.txt`, virtualenv, and test suite (`pytest`, `ruff`, `mypy`). See the individual service's
`README.md` for exact local (non-Docker) run instructions. The general pattern, from inside any service
directory:

```bash
python -m venv .venv
.venv/Scripts/activate            # or: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head              # Postgres-backed services only
pytest -q
ruff check src tests
uvicorn <service>.main:app --reload --port <its-port>
```

The frontend (`frontend/`) is a standard Next.js app:

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000, talks to whatever NEXT_PUBLIC_API_BASE_URL points at
npm test
npm run build
```

`NEXT_PUBLIC_*` variables are compiled into the client bundle at **build time** — setting them only as a
Docker runtime `environment:` var has no effect; `docker-compose.yml`'s `frontend` build args are what
actually control the shipped bundle (mocks on/off, API base URL, Stripe publishable key).

## Where to look for specific flows

- **Signup → verification → login → account creation:** `auth-service` issues the account; `tenant-service`
  auto-creates an Individual account on `user.registered`, or a Team account via `POST /api/v1/accounts`.
- **Forgot password:** `auth-service` generates a 6-digit OTP, publishes `user.password_reset_requested`;
  `notification-service` emails it.
- **Buy credits:** frontend → `billing-service`'s `/billing/credits/checkout` (dynamic Stripe Checkout
  Session, no pre-created Price ID) → Stripe webhook → `billing-service` outbox → `credits-service` grants
  the ledger entry.
- **Marketplace:** `credits-service` handles listing, reservation, Stripe escrow via `billing-service`, and
  the ledger transfer on confirm.
- **AI generation:** `ai-generation-service` streams OpenRouter tokens over Redis pub/sub; the gateway
  relays that as SSE to the browser; credits are deducted on completion.
- **Scheduling → LinkedIn:** `scheduler-service`'s Celery beat worker fires due posts, publishing
  `content.scheduled`; `social-publishing-service` consumes it and calls the LinkedIn API.
- **Scraper → content:** a completed research job's "Use in AI Studio" button seeds the AI Studio prompt
  with the scraped findings, so research directly feeds a generation.

## Deployment / AWS

Not yet implemented — deployment topology, AWS free-tier constraints, and any resulting tradeoffs will be
documented here once that work starts. `docker-compose.yml` has an inline note on what would need to change
(managed Postgres/Redis/RabbitMQ endpoints in place of `host.docker.internal`).
