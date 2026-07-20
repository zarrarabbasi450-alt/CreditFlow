from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from billing_service.models import Plan


class CheckoutRequest(BaseModel):
    plan: Literal["pro", "team", "enterprise"]
    seats: int = Field(default=1, ge=1, le=1000)


class PlanChangeRequest(BaseModel):
    plan: Plan
    seats: int = Field(default=1, ge=1, le=1000)
    proration_behavior: Literal["always_invoice", "create_prorations", "none"] = "always_invoice"


class RefundRequest(BaseModel):
    invoice_id: UUID
    amount: int | None = Field(default=None, ge=1)
    reason: Literal["duplicate", "fraudulent", "requested_by_customer"] = "requested_by_customer"


class EscrowCreateRequest(BaseModel):
    listing_id: UUID
    seller_account_id: UUID
    amount: int = Field(ge=1)
    currency: Literal["usd"] = "usd"


class EscrowResponse(BaseModel):
    payment_intent_id: str
    client_secret: str | None = None
    status: str


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    plan: str
    status: str
    seats: int
    current_period_end: datetime | None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    number: str | None
    status: str
    currency: str
    amount_due: int
    amount_paid: int
    hosted_invoice_url: str | None
    invoice_pdf: str | None
    issued_at: datetime


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    invoice_id: UUID
    amount: int
    currency: str
    reason: str
    status: str
    created_at: datetime


class UrlResponse(BaseModel):
    url: str


class BillingOverviewResponse(BaseModel):
    subscription: SubscriptionResponse
    invoices: list[InvoiceResponse]
    payment_methods_managed_by_stripe: bool = True
