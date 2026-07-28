from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from credits_service.api.dependencies import get_identity, require_owner
from credits_service.core.errors import CreditsError
from credits_service.models import CreditLedger
from credits_service.schemas.credits import (
    BalanceResponse,
    CreditConsumption,
    LedgerResponse,
    ListingCreate,
    ListingResponse,
    MarketplaceOverview,
    PurchaseConfirm,
    PurchaseRequest,
    PurchaseResponse,
    TransferResponse,
)
from credits_service.services.billing import BillingProtocol
from credits_service.services.credits import CreditsService
from credits_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])
Actor = Annotated[Identity, Depends(get_identity)]
Owner = Annotated[Identity, Depends(require_owner)]


def service(request: Request) -> CreditsService:
    return cast(CreditsService, request.app.state.credits)


def bearer_token(authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip()


async def ledger_responses(values: list[CreditLedger], account_id: UUID) -> list[LedgerResponse]:
    running = 0
    mapped: dict[UUID, int] = {}
    for entry in reversed(values):
        running += entry.amount
        mapped[entry.id] = running
    return [
        LedgerResponse(
            id=value.id,
            account_id=value.account_id,
            entry_type=value.entry_type,
            amount=value.amount,
            balance_after=mapped[value.id],
            description=value.description,
            counterparty_account_id=value.counterparty_account_id,
            created_at=value.created_at,
        )
        for value in values
        if value.account_id == account_id
    ]


@router.get("/internal/{account_id}/balance", response_model=BalanceResponse)
async def balance_internal(
    account_id: UUID, request: Request, authorization: str = Header()
) -> BalanceResponse:
    """Trusted service-to-service lookup — guarded by a shared secret, not a user
    JWT. Used by admin-service to build its per-account operational overview."""
    settings = request.app.state.settings
    token = authorization.removeprefix("Bearer ").strip()
    if not settings.internal_service_token or token != settings.internal_service_token:
        raise CreditsError(401, "INVALID_INTERNAL_TOKEN", "Internal service token is invalid")
    return BalanceResponse(account_id=account_id, balance=await service(request).balance(account_id))


@router.get("/balance", response_model=BalanceResponse)
async def balance(request: Request, actor: Actor) -> BalanceResponse:
    return BalanceResponse(
        account_id=actor.account_id, balance=await service(request).balance(actor.account_id)
    )


@router.get("/summary", response_model=BalanceResponse)
async def summary(request: Request, actor: Actor) -> BalanceResponse:
    return await balance(request, actor)


@router.post("/consume", response_model=BalanceResponse)
async def consume_credits(payload: CreditConsumption, request: Request, actor: Actor) -> BalanceResponse:
    remaining = await service(request).consume_credits(
        actor.account_id,
        actor.user_id,
        payload.amount,
        payload.reference_id,
        payload.description,
    )
    return BalanceResponse(account_id=actor.account_id, balance=remaining)


@router.get("/transactions", response_model=list[LedgerResponse])
async def transactions(
    request: Request, actor: Actor, limit: int = Query(default=100, ge=1, le=500)
) -> list[LedgerResponse]:
    values = await service(request).transactions(actor.account_id, limit)
    return await ledger_responses(values, actor.account_id)


@router.get("/overview", response_model=MarketplaceOverview)
async def overview(request: Request, actor: Actor) -> MarketplaceOverview:
    values = await service(request).transactions(actor.account_id)
    listings = await service(request).listings()
    return MarketplaceOverview(
        balance=await service(request).balance(actor.account_id),
        ledger=await ledger_responses(values, actor.account_id),
        listings=[ListingResponse.model_validate(value) for value in listings],
    )


@router.get("/marketplace/listings", response_model=list[ListingResponse])
async def listings(request: Request, actor: Actor) -> list[ListingResponse]:
    del actor
    return [ListingResponse.model_validate(value) for value in await service(request).listings()]


@router.post(
    "/marketplace/listings",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_listing(payload: ListingCreate, request: Request, owner: Owner) -> ListingResponse:
    value = await service(request).create_listing(owner.account_id, owner.user_id, payload)
    return ListingResponse.model_validate(value)


@router.delete("/marketplace/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_listing(listing_id: UUID, request: Request, owner: Owner) -> Response:
    await service(request).cancel_listing(listing_id, owner.account_id, owner.is_superadmin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/marketplace/purchases", response_model=PurchaseResponse)
async def purchase(
    payload: PurchaseRequest,
    request: Request,
    owner: Owner,
    authorization: str = Header(),
) -> PurchaseResponse:
    listing = await service(request).reserve_purchase(payload.listing_id, owner.account_id)
    billing = cast(BillingProtocol, request.app.state.billing)
    try:
        intent_id, secret, payment_status = await billing.create_escrow(
            bearer_token(authorization), listing.id, listing.seller_account_id, listing.price_cents
        )
        await service(request).set_payment_intent(listing.id, intent_id)
    except Exception:
        await service(request).release_reservation(listing.id)
        raise
    return PurchaseResponse(
        listing_id=listing.id,
        payment_intent_id=intent_id,
        client_secret=secret,
        status=payment_status,
    )


@router.post("/marketplace/purchases/{listing_id}/confirm", response_model=TransferResponse)
async def confirm_purchase(
    listing_id: UUID,
    payload: PurchaseConfirm,
    request: Request,
    owner: Owner,
    authorization: str = Header(),
) -> TransferResponse:
    payment_status = await cast(BillingProtocol, request.app.state.billing).capture_escrow(
        bearer_token(authorization), payload.payment_intent_id
    )
    if payment_status != "succeeded":
        return TransferResponse(transaction_id=UUID(int=0), listing_id=listing_id, status=payment_status)
    transaction_id = await service(request).complete_purchase(
        listing_id, owner.account_id, owner.user_id, payload.payment_intent_id
    )
    return TransferResponse(transaction_id=transaction_id, listing_id=listing_id, status="completed")


@router.delete("/marketplace/purchases/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_purchase(listing_id: UUID, request: Request, owner: Owner) -> Response:
    await service(request).release_reservation(listing_id, owner.account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
