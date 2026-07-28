"""Standalone worker process: consumes `scrape.requested` and runs the
recurring-job scan loop. Run alongside the API process:

    python -m scraper_service.worker

The API process (main.py) only serves HTTP endpoints and publishes
`scrape.requested` — it never executes a scrape itself. This process is
where jobs actually run (crawling, robots.txt checks, rate limiting,
SerpApi calls, and persisting results).
"""

import asyncio
import logging
from contextlib import suppress

from scraper_service.core.config import get_settings
from scraper_service.core.logging import configure_logging
from scraper_service.database import MongoScraperRepository
from scraper_service.services.crawler import HttpxCrawler, PlaywrightCrawler
from scraper_service.services.rabbitmq import RabbitMQService
from scraper_service.services.rate_limiter import DomainRateLimiter
from scraper_service.services.robots import RobotsChecker
from scraper_service.services.scraper import ScraperService
from scraper_service.services.serp import SerpApiClient

logger = logging.getLogger(__name__)


async def recurring_scan_loop(scraper: ScraperService, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        rescanned = await scraper.scan_due_recurring_jobs()
        if rescanned:
            logger.info("Re-dispatched %s due recurring scrape job(s)", rescanned)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting scraper-service worker (engine=%s)", settings.scraper_engine)

    repository = MongoScraperRepository(settings.mongodb_url, settings.mongodb_database)
    events = RabbitMQService(settings.rabbitmq_url)
    crawler_args = (
        settings.scraper_user_agent,
        settings.request_timeout_seconds,
        settings.max_document_chars,
    )
    crawler = (
        PlaywrightCrawler(*crawler_args)
        if settings.scraper_engine == "playwright"
        else HttpxCrawler(*crawler_args)
    )
    serp = SerpApiClient(
        settings.serpapi_api_key,
        settings.serpapi_base_url,
        settings.serpapi_engine,
        settings.request_timeout_seconds,
    )
    robots = RobotsChecker(settings.scraper_user_agent, settings.robots_cache_seconds)
    rate_limiter = DomainRateLimiter(settings.min_request_interval_seconds)
    scraper = ScraperService(
        repository,
        events,
        crawler,
        serp,
        robots,
        rate_limiter,
        settings.max_pages_per_job,
        settings.publish_max_attempts,
    )

    await events.start(scraper.consume)
    scan_task = asyncio.create_task(
        recurring_scan_loop(scraper, settings.recurring_scan_interval_seconds), name="scraper-recurring-scan"
    )
    logger.info("Worker ready: consuming scrape.requested")
    try:
        await asyncio.Event().wait()
    finally:
        scan_task.cancel()
        with suppress(asyncio.CancelledError):
            await scan_task
        await events.close()
        await crawler.close()
        await serp.close()
        await scraper.close()
        await repository.close()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    main()
