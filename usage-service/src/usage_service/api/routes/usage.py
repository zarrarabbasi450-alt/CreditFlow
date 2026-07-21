from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from usage_service.api.dependencies import get_identity
from usage_service.core.errors import UsageError
from usage_service.schemas.usage import (
    QuotaCheckRequest,
    QuotaCheckResponse,
    UsageLedgerResponse,
    UsageSummary,
)
from usage_service.services.identity import Identity
from usage_service.services.usage import UsageService

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])
Actor = Annotated[Identity, Depends(get_identity)]


def service(request: Request) -> UsageService:
    return cast(UsageService, request.app.state.usage)


def scoped_account(actor: Identity, account_id: UUID | None) -> UUID:
    if account_id is None or account_id == actor.account_id:
        return actor.account_id
    if not actor.is_superadmin:
        raise UsageError(403, "ACCOUNT_ACCESS_DENIED", "Usage is restricted to the active account")
    return account_id


@router.post("/quota/check", response_model=QuotaCheckResponse, operation_id="check_usage_quota")
async def check_quota(payload: QuotaCheckRequest, request: Request, actor: Actor) -> QuotaCheckResponse:
    allowed, current, period = await service(request).check_quota(actor.account_id, payload.estimated_tokens)
    quota = request.app.state.settings.default_monthly_token_quota
    used = max(0, current - payload.estimated_tokens) if allowed else current
    return QuotaCheckResponse(
        allowed=allowed,
        tokens_used=used,
        tokens_reserved=payload.estimated_tokens if allowed else 0,
        quota_tokens=quota,
        remaining_tokens=max(0, quota - current),
        period=period,
    )


@router.get("/summary", response_model=UsageSummary, operation_id="get_usage_summary")
async def summary(
    request: Request,
    actor: Actor,
    account_id: Annotated[UUID | None, Query()] = None,
) -> UsageSummary:
    return await service(request).summary(scoped_account(actor, account_id))


@router.get("/ledger", response_model=list[UsageLedgerResponse], operation_id="get_usage_ledger")
async def ledger(
    request: Request,
    actor: Actor,
    account_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[UsageLedgerResponse]:
    values = await service(request).ledger(scoped_account(actor, account_id), limit)
    return [UsageLedgerResponse.model_validate(value) for value in values]
