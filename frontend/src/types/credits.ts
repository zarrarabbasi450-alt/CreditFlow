export interface CreditLedgerEntry {
  id: string;
  accountId: string;
  type: "Grant" | "Usage" | "Trade" | "Refund clawback" | "Adjustment";
  amount: number;
  balanceAfter: number;
  description: string;
  createdAt: string;
}
export interface MarketplaceListing {
  id: string;
  sellerAccountId: string;
  credits: number;
  priceCents: number;
  status: "Open" | "Reserved" | "Sold" | "Canceled" | "Expired";
  expiresAt: string;
}
export interface CreditsOverview {
  view: import("./api").ProductView;
  balance: number;
  ledger: CreditLedgerEntry[];
  listings: MarketplaceListing[];
}
export interface ListingCreate {
  credits: number;
  priceCents: number;
  expiresInDays?: number;
}
