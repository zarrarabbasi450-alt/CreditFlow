# CreditFlow Frontend

The frontend-first CreditFlow product is a Next.js App Router application backed by realistic in-browser mock contracts. It covers landing and pricing, authentication, tenant/team access, billing, credits and marketplace, usage, AI streaming, content, recurring scheduling, LinkedIn text/image publishing, scraping, notifications, settings, and SuperAdmin operations.

## Start locally

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. Demo credentials are prefilled on the login screen. All demo roles use `Password123!`:

- `owner@orionmedia.com`
- `admin@orionmedia.com`
- `member@orionmedia.com`
- `superadmin@creditflow.com`

Use the role selector in the authenticated top bar to exercise role navigation during development.

## Validation

```bash
npm run format:check
npm run lint
npm run type-check
npm test
npm run build
npm run test:e2e
docker build -t creditflow-frontend:local .
```

All HTTP traffic is centralized in `src/lib/api/` and currently intercepted by MSW in development. Set `NEXT_PUBLIC_ENV=production` when the API Gateway contracts become available.
