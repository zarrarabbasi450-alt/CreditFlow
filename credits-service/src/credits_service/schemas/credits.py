from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from credits_service.models import LedgerType, ListingStatus


class LedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    entry_type: LedgerType
    amount: int
    balance_after: int
    description: str
    counterparty_account_id: UUID | None
    created_at: datetime


class BalanceResponse(BaseModel):
    account_id: UUID
    balance: int


class ListingCreate(BaseModel):
    credits: int = Field(gt=0)
    price_cents: int = Field(gt=0)
    expires_in_days: int = Field(default=30, ge=1, le=90)


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    seller_account_id: UUID
    credits: int
    price_cents: int
    status: ListingStatus
    buyer_account_id: UUID | None
    expires_at: datetime
    created_at: datetime


class PurchaseRequest(BaseModel):
    listing_id: UUID


class PurchaseResponse(BaseModel):
    listing_id: UUID
    payment_intent_id: str
    client_secret: str | None
    status: str


class PurchaseConfirm(BaseModel):
    payment_intent_id: str = Field(min_length=1)


class TransferResponse(BaseModel):
    transaction_id: UUID
    listing_id: UUID
    status: str


class MarketplaceOverview(BaseModel):
    balance: int
    ledger: list[LedgerResponse]
    listings: list[ListingResponse]
