from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from scheduler_service.api.dependencies import get_identity, get_scheduler_service
from scheduler_service.schemas.scheduler import (
    CalendarResponse,
    ScheduleCreate,
    ScheduledPostResponse,
    SchedulerSummary,
    ScheduleUpdate,
)
from scheduler_service.services.identity import Identity
from scheduler_service.services.scheduler import SchedulerService

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


@router.get("", operation_id="calendar", response_model=CalendarResponse)
async def calendar(
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
    range_start: Annotated[datetime | None, Query(alias="start")] = None,
    range_end: Annotated[datetime | None, Query(alias="end")] = None,
    timezone: str = "UTC",
) -> CalendarResponse:
    start = range_start or datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = range_end or (start + timedelta(days=45))
    return await service.calendar(identity, start, end, timezone)


@router.post("", operation_id="schedule_content", response_model=ScheduledPostResponse)
async def schedule_content(
    payload: ScheduleCreate,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> ScheduledPostResponse:
    return await service.schedule(
        identity, payload.content_id, payload.title, payload.publish_at, payload.timezone
    )


@router.get("/summary", operation_id="scheduler_summary", response_model=SchedulerSummary)
async def summary(
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> SchedulerSummary:
    return await service.summary(identity)


@router.get("/{schedule_id}", operation_id="get_schedule", response_model=ScheduledPostResponse)
async def get_schedule(
    schedule_id: UUID,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
    timezone: str = "UTC",
) -> ScheduledPostResponse:
    return await service.get(identity, schedule_id, timezone)


@router.patch("/{schedule_id}", operation_id="reschedule_content", response_model=ScheduledPostResponse)
async def reschedule_content(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> ScheduledPostResponse:
    return await service.reschedule(identity, schedule_id, payload.publish_at, payload.timezone)


@router.delete("/{schedule_id}", operation_id="cancel_schedule", response_model=ScheduledPostResponse)
async def cancel_schedule(
    schedule_id: UUID,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
    identity: Annotated[Identity, Depends(get_identity)],
    timezone: str = "UTC",
) -> ScheduledPostResponse:
    return await service.cancel(identity, schedule_id, timezone)
