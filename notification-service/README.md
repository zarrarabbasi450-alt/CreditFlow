# CreditFlow Notification Service

Sends transactional email (and optional Slack alerts) in response to platform events, and
logs every notification attempt to Postgres for auditing.

## Responsibilities

- Consumes `user.registered`, `member.invited`, `member.joined`, `invoice.paid`,
  `payment.failed`, `post.published`, `post.failed`, and `usage.threshold_reached` off the
  shared `creditflow.events` exchange.
- Resolves a recipient email for each event: `user.registered` / `member.invited` carry the
  email directly in their payload; account-scoped events (`invoice.paid`, `payment.failed`,
  `post.*`, `usage.threshold_reached`) resolve the account owner's email via tenant-service
  (`/accounts/internal/{account_id}/owner`) and auth-service
  (`/auth/internal/users/{user_id}`); `member.joined` resolves the joining user directly.
- Sends email via either [Resend](https://resend.com) or the Gmail API (OAuth), selected by
  `EMAIL_PROVIDER` — no self-hosted SMTP. `member.joined` has no email template by design
  (it's logged for the audit feed only).
- For `payment.failed`, `post.failed`, and `usage.threshold_reached`, also posts an alert to a
  Slack Incoming Webhook, independent of whether the email succeeded.
- Logs every attempt (sent/failed/skipped, per channel) to `notification_log` and emits
  `notification.sent` on successful delivery.
- Exposes `GET /api/v1/notifications` (account-scoped, superadmin sees all) for the frontend's
  notification feed.

## Local setup

1. Copy `.env.example` to `.env`.
2. `INTERNAL_SERVICE_TOKEN` must match the same value configured in auth-service and
   tenant-service's `.env` files (used to call their internal directory-lookup endpoints).
3. Set `EMAIL_PROVIDER` to `resend` or `gmail`:
   - **`resend`**: get a free [Resend](https://resend.com) API key and set `RESEND_API_KEY`.
     Without a verified custom sending domain, Resend's sandbox mode only delivers to the
     account's own signup email — every other recipient is rejected with a 403.
   - **`gmail`**: sends via the Gmail API as a real Gmail account (no domain needed, works for
     any recipient, subject to Gmail's own ~500/day sending cap). Requires:
     1. A Google Cloud project with the Gmail API enabled and an OAuth consent screen
        (scope `https://www.googleapis.com/auth/gmail.send`) published to production (Testing
        status caps refresh tokens at 7 days).
     2. An OAuth client (type "Desktop app") → `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.
     3. A one-time authorization flow to mint `GOOGLE_REFRESH_TOKEN` (visit the Google
        consent URL for that client with `scope=gmail.send&access_type=offline&prompt=consent`,
        then exchange the returned `code` at `https://oauth2.googleapis.com/token`).
     4. `GMAIL_SENDER_EMAIL` — the Gmail address that authorized the app.
   Whichever provider is misconfigured fails with a `503 EMAIL_PROVIDER_NOT_CONFIGURED` error
   (still logged as `failed`, doesn't crash the consumer).
4. Optional: create a [Slack Incoming Webhook](https://api.slack.com/messaging/webhooks) and
   set `SLACK_WEBHOOK_URL` to enable ops alerts for failures/thresholds. Without it, Slack
   sends are skipped with a `503 SLACK_NOT_CONFIGURED` error (logged as `failed`, does not
   block the email).
5. Run `alembic upgrade head` to create the `notifications` schema.

## Run

```powershell
cd C:\Development\CreditFlow\notification-service
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m pip install -e .
python -m uvicorn notification_service.main:app --reload --port 8111
```

The RabbitMQ consumer runs inline inside the API process's lifespan — no separate worker
process is needed.
