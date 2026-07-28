from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from admin_service.api.dependencies import get_admin_service, get_identity
from admin_service.schemas.admin import AccountSummary, AdminOverview, AuditEntry, SessionItem
from admin_service.services.admin import AdminService
from admin_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
Actor = Annotated[Identity, Depends(get_identity)]
Service = Annotated[AdminService, Depends(get_admin_service)]


@router.get("/overview", response_model=AdminOverview, operation_id="get_admin_overview")
async def overview(identity: Actor, service: Service) -> AdminOverview:
    return await service.overview(identity)


@router.get("/sessions", response_model=list[SessionItem], operation_id="list_admin_sessions")
async def list_sessions(
    identity: Actor, service: Service, account_id: Annotated[UUID | None, Query()] = None
) -> list[SessionItem]:
    return await service.list_sessions(identity, account_id)


@router.delete("/sessions/{jti}", status_code=status.HTTP_204_NO_CONTENT, operation_id="revoke_admin_session")
async def revoke_session(jti: str, identity: Actor, service: Service) -> Response:
    await service.revoke_session(identity, jti)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/accounts/{account_id}/summary", response_model=AccountSummary, operation_id="get_account_summary"
)
async def account_summary(account_id: UUID, identity: Actor, service: Service) -> AccountSummary:
    return await service.account_summary(identity, account_id)


@router.get("/audit", response_model=list[AuditEntry], operation_id="list_admin_audit")
async def list_audit(
    identity: Actor,
    service: Service,
    account_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEntry]:
    return await service.list_audit(identity, account_id, limit)
