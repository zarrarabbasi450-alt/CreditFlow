from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from billing_service.api.dependencies import require_owner
from billing_service.schemas.billing import (
    BillingOverviewResponse,
    CheckoutRequest,
    CreditCheckoutRequest,
    EscrowCreateRequest,
    EscrowResponse,
    InvoiceResponse,
    PlanChangeRequest,
    RefundRequest,
    RefundResponse,
    SubscriptionResponse,
    UrlResponse,
)
from billing_service.services.billing import BillingService
from billing_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
Owner = Annotated[Identity, Depends(require_owner)]


def service(request: Request) -> BillingService:
    return cast(BillingService, request.app.state.billing)


@router.get("/overview", response_model=BillingOverviewResponse)
async def overview(request: Request, owner: Owner) -> BillingOverviewResponse:
    subscription = await service(request).subscription(owner.account_id)
    invoices = await service(request).invoices(owner.account_id)
    return BillingOverviewResponse(
        subscription=SubscriptionResponse.model_validate(subscription),
        invoices=[InvoiceResponse.model_validate(value) for value in invoices],
    )


@router.get("/invoices", response_model=list[InvoiceResponse])
async def invoices(request: Request, owner: Owner) -> list[InvoiceResponse]:
    return [
        InvoiceResponse.model_validate(value) for value in await service(request).invoices(owner.account_id)
    ]


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(request: Request, owner: Owner) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(await service(request).subscription(owner.account_id))


@router.post("/checkout", response_model=UrlResponse)
async def checkout(payload: CheckoutRequest, request: Request, owner: Owner) -> UrlResponse:
    return UrlResponse(url=await service(request).checkout(owner.account_id, payload))


@router.post("/credits/checkout", response_model=UrlResponse)
async def credit_checkout(payload: CreditCheckoutRequest, request: Request, owner: Owner) -> UrlResponse:
    return UrlResponse(url=await service(request).credit_checkout(owner.account_id, payload))


@router.post("/portal", response_model=UrlResponse)
async def portal(request: Request, owner: Owner) -> UrlResponse:
    return UrlResponse(url=await service(request).portal(owner.account_id))


@router.post("/escrows", response_model=EscrowResponse)
async def create_escrow(payload: EscrowCreateRequest, request: Request, owner: Owner) -> EscrowResponse:
    value = await service(request).create_escrow(owner.account_id, payload)
    return EscrowResponse(
        payment_intent_id=str(value["id"]),
        client_secret=str(value["client_secret"]) if value.get("client_secret") else None,
        status=str(value["status"]),
    )


@router.post("/escrows/{payment_intent_id}/capture", response_model=EscrowResponse)
async def capture_escrow(payment_intent_id: str, request: Request, owner: Owner) -> EscrowResponse:
    value = await service(request).capture_escrow(owner.account_id, payment_intent_id)
    return EscrowResponse(payment_intent_id=str(value["id"]), status=str(value["status"]))


@router.patch("/subscription", response_model=SubscriptionResponse)
async def change_subscription(
    payload: PlanChangeRequest, request: Request, owner: Owner
) -> SubscriptionResponse:
    value = await service(request).change_plan(
        owner.account_id, payload, request.headers.get("x-correlation-id", "api")
    )
    return SubscriptionResponse.model_validate(value)


@router.post("/refunds", response_model=RefundResponse)
async def refund(payload: RefundRequest, request: Request, owner: Owner) -> RefundResponse:
    value = await service(request).refund(
        owner.account_id, payload, request.headers.get("x-correlation-id", "api")
    )
    return RefundResponse.model_validate(value)
