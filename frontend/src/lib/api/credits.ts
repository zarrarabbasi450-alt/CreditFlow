import { request } from "./client";
import type { CreditLedgerEntry, CreditsOverview, ListingCreate, MarketplaceListing } from "@/types";
type BackendLedger = {
  id: string;
  account_id: string;
  entry_type: string;
  amount: number;
  balance_after: number;
  description: string;
  created_at: string;
};
type BackendListing = {
  id: string;
  seller_account_id: string;
  credits: number;
  price_cents: number;
  status: string;
  expires_at: string;
};
type BackendOverview = { balance: number; ledger: BackendLedger[]; listings: BackendListing[] };
const label = (value: string) =>
  (value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ")) as CreditLedgerEntry["type"];
const listing = (value: BackendListing): MarketplaceListing => ({
  id: value.id,
  sellerAccountId: value.seller_account_id,
  credits: value.credits,
  priceCents: value.price_cents,
  status: (value.status.charAt(0).toUpperCase() + value.status.slice(1)) as MarketplaceListing["status"],
  expiresAt: value.expires_at,
});
export const getCredits = async (): Promise<CreditsOverview> => {
  const value = await request<BackendOverview>({ url: "/credits/overview", method: "GET" });
  return {
    view: {
      title: "Credits",
      eyebrow: "Balance & marketplace",
      description: "Review your append-only credit ledger and trade surplus credits.",
      action: "List credits",
    },
    balance: value.balance,
    ledger: value.ledger.map((entry) => ({
      id: entry.id,
      accountId: entry.account_id,
      type: label(entry.entry_type),
      amount: entry.amount,
      balanceAfter: entry.balance_after,
      description: entry.description,
      createdAt: entry.created_at,
    })),
    listings: value.listings.map(listing),
  };
};
export const createCreditListing = async (value: ListingCreate) =>
  listing(
    await request<BackendListing>({
      url: "/credits/marketplace/listings",
      method: "POST",
      data: {
        credits: value.credits,
        price_cents: value.priceCents,
        expires_in_days: value.expiresInDays ?? 30,
      },
    }),
  );
export const cancelCreditListing = (id: string) =>
  request<void>({ url: `/credits/marketplace/listings/${id}`, method: "DELETE" });
export const purchaseCredits = (listingId: string) =>
  request<{ payment_intent_id: string; client_secret: string | null; status: string }>({
    url: "/credits/marketplace/purchases",
    method: "POST",
    data: { listing_id: listingId },
  });
export const confirmCreditPurchase = (listingId: string, paymentIntentId: string) =>
  request<{ transaction_id: string; listing_id: string; status: string }>({
    url: `/credits/marketplace/purchases/${listingId}/confirm`,
    method: "POST",
    data: { payment_intent_id: paymentIntentId },
  });
export const cancelCreditPurchase = (listingId: string) =>
  request<void>({ url: `/credits/marketplace/purchases/${listingId}`, method: "DELETE" });
