from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from scraper_service.api.routes.operations import router as operations_router
from scraper_service.api.routes.scraper import router as scraper_router
from scraper_service.core.config import get_settings
from scraper_service.core.errors import ScraperError, scraper_error_handler
from scraper_service.core.logging import configure_logging
from scraper_service.database import MongoScraperRepository, ScraperRepositoryProtocol
from scraper_service.middleware import RequestContextMiddleware
from scraper_service.services.crawler import CrawlerProtocol, HttpxCrawler, PlaywrightCrawler
from scraper_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from scraper_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from scraper_service.services.rate_limiter import DomainRateLimiter
from scraper_service.services.robots import RobotsChecker
from scraper_service.services.scraper import ScraperService
from scraper_service.services.serp import SerpApiClient, SerpClientProtocol


async def exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if isinstance(exc, ScraperError):
        return await scraper_error_handler(request, exc)
    return ORJSONResponse(
        {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Unexpected scraper error"}},
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """API process only: serves job endpoints and publishes `scrape.requested`.

    Execution (consuming `scrape.requested`, running crawls, and the recurring-job
    scan loop) happens in the separate worker process — see `scraper_service.worker`.
    Run both `uvicorn scraper_service.main:app` and `python -m scraper_service.worker`
    for scrape jobs to actually complete.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    repository = getattr(app.state, "repository", None) or MongoScraperRepository(
        settings.mongodb_url, settings.mongodb_database
    )
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    crawler_args = (
        settings.scraper_user_agent,
        settings.request_timeout_seconds,
        settings.max_document_chars,
    )
    crawler = getattr(app.state, "crawler", None) or (
        PlaywrightCrawler(*crawler_args)
        if settings.scraper_engine == "playwright"
        else HttpxCrawler(*crawler_args)
    )
    serp = getattr(app.state, "serp", None) or SerpApiClient(
        settings.serpapi_api_key,
        settings.serpapi_base_url,
        settings.serpapi_engine,
        settings.request_timeout_seconds,
    )
    robots = RobotsChecker(settings.scraper_user_agent, settings.robots_cache_seconds)
    rate_limiter = DomainRateLimiter(settings.min_request_interval_seconds)
    scraper = getattr(app.state, "scraper", None) or ScraperService(
        repository,
        events,
        crawler,
        serp,
        robots,
        rate_limiter,
        settings.max_pages_per_job,
        settings.publish_max_attempts,
    )
    app.state.settings = settings
    app.state.repository = repository
    app.state.events = events
    app.state.crawler = crawler
    app.state.serp = serp
    app.state.scraper = scraper
    app.state.identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    try:
        yield
    finally:
        await events.close()
        await crawler.close()
        await serp.close()
        await scraper.close()
        await repository.close()


def create_app(
    repository: ScraperRepositoryProtocol | None = None,
    events: EventBusProtocol | None = None,
    crawler: CrawlerProtocol | None = None,
    serp: SerpClientProtocol | None = None,
    identity_service: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Scraper Service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    if repository is not None:
        app.state.repository = repository
    if events is not None:
        app.state.events = events
    if crawler is not None:
        app.state.crawler = crawler
    if serp is not None:
        app.state.serp = serp
    if identity_service is not None:
        app.state.identity_service = identity_service
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ScraperError, exception_handler)
    app.include_router(operations_router)
    app.include_router(scraper_router)
    return app


app = create_app()
