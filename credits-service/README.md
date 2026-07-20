# CreditFlow Credits & Marketplace Service

Owns the append-only credit ledger, balances, transaction history, marketplace listings, and atomic credit transfers.
It consumes `invoice.paid` and `refund.issued` from RabbitMQ and publishes `credits.credited`,
`credits.debited`, `credits.balance_changed`, and `credits.low_balance`.

The service owns the PostgreSQL `credits` schema. Owner and SuperAdmin identities can create listings and
purchase marketplace credits; authenticated account members can read their own balance and ledger.

Run locally:

```powershell
alembic upgrade head
python -m uvicorn credits_service.main:app --reload --port 8004
```
