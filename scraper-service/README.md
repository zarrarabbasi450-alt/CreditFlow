# CreditFlow Scraper Service

Runs on-demand and recurring web-scraping jobs for trend/competitor research, feeding raw
documents into the content-generation pipeline.

## Responsibilities

- Accepts scrape job requests (`url`, `serp`, or `research` job types) via the API, and
  dispatches them through RabbitMQ (`scrape.requested`) so the HTTP request never blocks on
  execution — the API process only creates the job and publishes the event.
- `url` jobs: fetch a target page (and up to `max_pages` same-domain links), honouring
  `robots.txt` and a per-domain rate limit, and extract title/text/links.
- `serp` jobs: query [SerpApi](https://serpapi.com) for search-engine results (trend/competitor
  keyword data) without scraping Google/Bing directly — keeps this ToS/robots.txt-safe.
- `research` jobs: given a free-text question, find the top sources via SerpApi, scrape each
  (same robots.txt/rate-limit rules as `url` jobs), and synthesize a Markdown answer with
  citations (`job.answer` / `job.answer_html`). `url` jobs also get an `answer` (a digest of
  the page(s) fetched), so every job type produces something displayable.
- Stores raw scraped documents in MongoDB (`scraped_documents` collection, flexible schema) —
  the only service in the platform authorized to use MongoDB; every other service uses the
  shared PostgreSQL instance.
- Emits `scrape.completed` / `scrape.failed`; consumes `scrape.requested`.
- Supports recurring jobs (`interval_hours`) via an internal scan loop that re-dispatches due
  jobs — no external cron needed.

## API process vs. worker process

This service runs as **two separate processes**:

- `scraper_service.main:app` (FastAPI, `uvicorn`) — serves job endpoints (`create`, `get`,
  `cancel`, `list documents`) and publishes `scrape.requested`. It never scrapes anything
  itself.
- `scraper_service.worker` — consumes `scrape.requested`, does the actual crawling/SerpApi
  calls/robots.txt checks/rate limiting, persists results, and runs the recurring-job scan
  loop that re-dispatches due jobs.

**Both must be running** for scrape jobs to complete — the API alone will accept and queue
jobs that stay `queued` forever without the worker.

## Scraping engine

Two interchangeable engines behind the same `CrawlerProtocol`, selected via `SCRAPER_ENGINE`:

- `httpx` (default): fast, dependency-light, no browser required. Cannot execute
  client-side JavaScript. Good for local dev.
- `playwright`: real headless Chromium, renders JS. The Dockerfile installs Chromium
  (`playwright install --with-deps chromium`) for this mode; running it locally outside
  Docker requires the same one-time install (see below).

## Local setup

1. Copy `.env.example` to `.env`.
2. Get a SerpApi key at https://serpapi.com (free tier available) and set `SERPAPI_API_KEY`.
   Without it, `serp` job types return a `503 SERPAPI_NOT_CONFIGURED` error; `url` jobs work
   regardless.
3. `INTERNAL_SERVICE_TOKEN` should match the same value configured in the other services'
   `.env` files (used for trusted service-to-service calls).
4. Ensure MongoDB is reachable at `MONGODB_URL` (e.g. `docker run -d --name creditflow-mongo
   -p 27017:27017 mongo:7`). No migrations to run — Mongo is schemaless.
5. Only needed for `SCRAPER_ENGINE=playwright` (default is `httpx`, no browser required):
   install the Chromium browser once with `python -m playwright install chromium`.

## Run

Two terminals — both processes must be running:

```powershell
# Terminal 1: API
cd C:\Development\CreditFlow\scraper-service
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m pip install -e .
python -m uvicorn scraper_service.main:app --reload --port 8110
```

```powershell
# Terminal 2: worker (runs the actual scrape jobs)
cd C:\Development\CreditFlow\scraper-service
python -m scraper_service.worker
```
