from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from tenant_service.api.dependencies import get_actor
from tenant_service.schemas.accounts import MemberResponse
from tenant_service.services.accounts import AccountService
from tenant_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/invites", tags=["invitations"])
Actor = Annotated[Identity, Depends(get_actor)]


@router.post("/{token}/accept", response_model=MemberResponse, operation_id="accept_account_invite")
async def accept_account_invite(token: str, request: Request, actor: Actor) -> MemberResponse:
    service = cast(AccountService, request.app.state.accounts)
    member = await service.accept_invite(token, actor.user_id)
    return MemberResponse.model_validate(member)
