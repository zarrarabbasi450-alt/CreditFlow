export interface Subscription {
  id: string;
  accountId: string;
  plan: "Free" | "Pro" | "Team" | "Enterprise";
  status: "Active" | "PastDue" | "Canceling" | "Canceled";
  seats: number;
  amountCents: number;
  currency: string;
  renewsAt: string;
}
export interface Invoice {
  id: string;
  accountId: string;
  number: string;
  amountCents: number;
  currency: string;
  status: "Paid" | "Open" | "Void";
  issuedAt: string;
  paymentMethodLast4: string;
  hostedUrl?: string;
  pdfUrl?: string;
}
export interface PaymentMethod {
  id: string;
  brand: string;
  last4: string;
  expiresMonth: number;
  expiresYear: number;
  isDefault: boolean;
}
export interface BillingOverview {
  view: import("./api").ProductView;
  subscription: Subscription;
  invoices: Invoice[];
  paymentMethods: PaymentMethod[];
}
