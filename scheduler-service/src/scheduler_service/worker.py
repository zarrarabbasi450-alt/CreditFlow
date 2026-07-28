import asyncio
from collections.abc import Callable
from typing import cast

from celery import Celery

from scheduler_service.core.config import get_settings
from scheduler_service.database import Database
from scheduler_service.services.rabbitmq import RabbitMQService
from scheduler_service.services.redis_lock import RedisLockService
from scheduler_service.services.scheduler import SchedulerService

settings = get_settings()
celery_app = Celery(
    "scheduler_service", broker=settings.celery_broker_url, backend=settings.celery_result_backend
)
celery_app.conf.beat_schedule = {
    "scan-due-scheduled-posts": {
        "task": "scheduler_service.scan_due_posts",
        "schedule": settings.due_scan_interval_seconds,
    }
}
celery_app.conf.timezone = "UTC"


async def _scan_due_posts() -> int:
    database = Database(settings.database_url)
    events = RabbitMQService(settings.rabbitmq_url)
    locks = RedisLockService(settings.redis_url)
    service = SchedulerService(database.sessions, events, locks, settings.schedule_lock_ttl_seconds)
    try:
        return await service.fire_due()
    finally:
        await events.close()
        await locks.close()
        await database.close()


task = cast(
    Callable[[Callable[[], int]], Callable[[], int]], celery_app.task(name="scheduler_service.scan_due_posts")
)


@task
def scan_due_posts() -> int:
    return asyncio.run(_scan_due_posts())
