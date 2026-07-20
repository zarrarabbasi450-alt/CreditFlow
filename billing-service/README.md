# CreditFlow Billing Service

FastAPI service owning Stripe customers, Checkout subscriptions, plan changes with proration, invoices, refunds, webhook persistence, dunning, and the transactional outbox.

## Local setup

1. Copy `.env.example` to `.env` and replace every `CHANGE_ME` value.
2. Create Stripe test-mode recurring Prices for Pro and Team and put their `price_...` IDs in `.env`.
3. Install: `python -m pip install -r requirements-dev.txt`.
4. Migrate: `alembic upgrade head`.
5. Run: `uvicorn billing_service.main:app --reload --port 8003`.

Payment methods are managed by Stripe Checkout and the Stripe Billing Portal. Checkout uses dynamic payment methods, so Stripe displays every compatible method enabled for the Stripe account, customer location, currency, and subscription mode without CreditFlow storing payment credentials.

The API Gateway remains the only public endpoint and verifies Stripe webhook signatures before publishing `billing.#` events. Billing Service persists each provider event before applying it.

All billing views and mutations are Owner-only because they expose or change financial data;
SuperAdmin has the documented platform-wide bypass. Billing verifies the same RS256 issuer, audience,
expiry, token type, account role, and platform role as the gateway. Tenant `account.created` events are
accepted in the shared CreditFlow event envelope and create the Stripe customer record for that account.
