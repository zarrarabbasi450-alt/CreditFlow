from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from tenant_service.api.dependencies import get_actor
from tenant_service.schemas.accounts import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    InviteCreate,
    InviteResponse,
    MemberResponse,
    RoleUpdate,
)
from tenant_service.services.accounts import AccountService
from tenant_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])
Actor = Annotated[Identity, Depends(get_actor)]


def service(request: Request) -> AccountService:
    return cast(AccountService, request.app.state.accounts)


@router.post(
    "", response_model=AccountResponse, status_code=status.HTTP_201_CREATED, operation_id="create_account"
)
async def create_account(payload: AccountCreate, request: Request, actor: Actor) -> AccountResponse:
    account = await service(request).create(payload, actor.user_id)
    return AccountResponse.model_validate(account)


@router.get("/my", response_model=list[AccountResponse], operation_id="list_my_accounts")
async def list_my_accounts(request: Request, actor: Actor) -> list[AccountResponse]:
    accounts = await service(request).list_for_user(actor)
    return [AccountResponse.model_validate(account) for account in accounts]


@router.get("/{account_id}", response_model=AccountResponse, operation_id="get_account")
async def get_account(account_id: UUID, request: Request, actor: Actor) -> AccountResponse:
    account = await service(request).get(account_id, actor)
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse, operation_id="update_account")
async def update_account(
    account_id: UUID, payload: AccountUpdate, request: Request, actor: Actor
) -> AccountResponse:
    account = await service(request).update(account_id, payload, actor)
    return AccountResponse.model_validate(account)


@router.get("/{account_id}/members", response_model=list[MemberResponse], operation_id="list_account_members")
async def list_account_members(account_id: UUID, request: Request, actor: Actor) -> list[MemberResponse]:
    members = await service(request).list_members(account_id, actor)
    return [MemberResponse.model_validate(member) for member in members]


@router.get(
    "/{account_id}/membership/me",
    response_model=MemberResponse,
    operation_id="get_my_account_membership",
)
async def get_my_account_membership(account_id: UUID, request: Request, actor: Actor) -> MemberResponse:
    member = await service(request).get_membership(account_id, actor)
    return MemberResponse.model_validate(member)


@router.patch(
    "/{account_id}/members/{user_id}",
    response_model=MemberResponse,
    operation_id="update_account_member_role",
)
async def update_account_member_role(
    account_id: UUID,
    user_id: UUID,
    payload: RoleUpdate,
    request: Request,
    actor: Actor,
) -> MemberResponse:
    member = await service(request).update_role(account_id, user_id, payload.role, actor)
    return MemberResponse.model_validate(member)


@router.delete(
    "/{account_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="remove_account_member",
)
async def remove_account_member(account_id: UUID, user_id: UUID, request: Request, actor: Actor) -> Response:
    await service(request).remove_member(account_id, user_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{account_id}/invite",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="invite_account_member",
)
async def invite_account_member(
    account_id: UUID, payload: InviteCreate, request: Request, actor: Actor
) -> InviteResponse:
    invitation = await service(request).invite(account_id, payload, actor)
    return InviteResponse.model_validate(invitation)


@router.get(
    "/{account_id}/invites",
    response_model=list[InviteResponse],
    operation_id="list_account_invites",
)
async def list_account_invites(account_id: UUID, request: Request, actor: Actor) -> list[InviteResponse]:
    invitations = await service(request).list_invites(account_id, actor)
    return [InviteResponse.model_validate(invitation) for invitation in invitations]


@router.get("", response_model=list[AccountResponse], operation_id="list_all_accounts")
async def list_all_accounts(request: Request, actor: Actor) -> list[AccountResponse]:
    accounts = await service(request).list_for_user(actor, all_accounts=True)
    return [AccountResponse.model_validate(account) for account in accounts]
