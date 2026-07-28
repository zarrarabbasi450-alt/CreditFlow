import { request } from "./client";
import type { BillingOverview, Invoice, ProductView, Subscription } from "@/types";

export type BillingPlan = "free" | "pro" | "team" | "enterprise";
type BackendSubscription = {
  id: string;
  account_id: string;
  plan: BillingPlan;
  status: string;
  seats: number;
  current_period_end: string | null;
};
type BackendInvoice = {
  id: string;
  number: string | null;
  status: string;
  currency: string;
  amount_due: number;
  amount_paid: number;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
  issued_at: string;
};
type BackendOverview = {
  subscription: BackendSubscription;
  invoices: BackendInvoice[];
  payment_methods_managed_by_stripe: boolean;
};

const planName = (plan: BackendSubscription["plan"]): Subscription["plan"] => {
  if (plan === "pro") return "Pro";
  if (plan === "team") return "Team";
  if (plan === "enterprise") return "Enterprise";
  return "Free";
};
const statusName = (status: string): Subscription["status"] => {
  if (status === "active") return "Active";
  if (status === "past_due") return "PastDue";
  if (status === "canceling") return "Canceling";
  return "Canceled";
};
const mapInvoice = (invoice: BackendInvoice, accountId: string): Invoice => ({
  id: invoice.id,
  accountId,
  number: invoice.number ?? invoice.id,
  amountCents: invoice.amount_paid || invoice.amount_due,
  currency: invoice.currency,
  status: invoice.status === "paid" ? "Paid" : invoice.status === "void" ? "Void" : "Open",
  issuedAt: invoice.issued_at,
  paymentMethodLast4: "Managed by Stripe",
  hostedUrl: invoice.hosted_invoice_url ?? undefined,
  pdfUrl: invoice.invoice_pdf ?? undefined,
});

export const getBilling = async (): Promise<BillingOverview> => {
  const result = await request<BackendOverview>({ url: "/billing/overview", method: "GET" });
  const subscription: Subscription = {
    id: result.subscription.id,
    accountId: result.subscription.account_id,
    plan: planName(result.subscription.plan),
    status: statusName(result.subscription.status),
    seats: result.subscription.seats,
    amountCents: 0,
    currency: "usd",
    renewsAt: result.subscription.current_period_end ?? "",
  };
  const invoices = result.invoices.map((invoice) => mapInvoice(invoice, subscription.accountId));
  const view: ProductView = {
    title: "Plans & billing",
    eyebrow: subscription.plan,
    description: "Choose the right CreditFlow plan, manage secure Stripe payments, and review every invoice.",
    action: subscription.plan === "Free" ? "Choose a plan" : "Manage billing",
    rows: invoices.map((invoice) => ({
      title: invoice.number,
      detail: new Intl.NumberFormat("en-US", { style: "currency", currency: invoice.currency }).format(
        invoice.amountCents / 100,
      ),
      status: invoice.status,
    })),
  };
  return { view, subscription, invoices, paymentMethods: [] };
};
export const getInvoices = async () => (await getBilling()).invoices;
export const createCheckout = (plan: Exclude<BillingPlan, "free">, seats = 1) =>
  request<{ url: string }>({ url: "/billing/checkout", method: "POST", data: { plan, seats } });
export const openBillingPortal = () => request<{ url: string }>({ url: "/billing/portal", method: "POST" });
export const createCreditPurchaseCheckout = (credits: number) =>
  request<{ url: string }>({ url: "/billing/credits/checkout", method: "POST", data: { credits } });
export const changePlan = (plan: BillingPlan, seats = 1) =>
  request<BackendSubscription>({
    url: "/billing/subscription",
    method: "PATCH",
    data: { plan, seats, proration_behavior: "always_invoice" },
  });
export const requestRefund = (invoiceId: string, amount?: number) =>
  request({
    url: "/billing/refunds",
    method: "POST",
    data: { invoice_id: invoiceId, amount, reason: "requested_by_customer" },
  });
