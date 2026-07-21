"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CreditCard, ExternalLink, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import {
  changePlan,
  createCheckout,
  getBilling,
  openBillingPortal,
  requestRefund,
  type BillingPlan,
} from "@/lib/api/billing";

const plans: Array<{
  id: BillingPlan;
  name: string;
  price: number;
  description: string;
  features: string[];
  recommended?: boolean;
}> = [
  {
    id: "free",
    name: "Free",
    price: 0,
    description: "Explore the essential CreditFlow workflow.",
    features: ["Core content workspace", "1 workspace seat", "Starter usage allowance", "Community support"],
  },
  {
    id: "pro",
    name: "Pro",
    price: 200,
    description: "For professionals scaling a consistent content engine.",
    features: [
      "Advanced AI generation",
      "Publishing and scheduling",
      "Higher usage limits",
      "Priority support",
    ],
    recommended: true,
  },
  {
    id: "team",
    name: "Team",
    price: 600,
    description: "For collaborative teams managing content together.",
    features: [
      "Everything in Pro",
      "Team roles and invitations",
      "Shared approval workflows",
      "Team-level usage insights",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 1000,
    description: "For organizations that need scale and control.",
    features: [
      "Everything in Team",
      "Enterprise usage capacity",
      "Advanced access controls",
      "Dedicated onboarding",
    ],
  },
];

export function BillingManagement({ subsection }: { subsection?: string }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const billing = useQuery({ queryKey: ["billing"], queryFn: getBilling });
  const redirect = useMutation({
    mutationFn: async (action: "portal" | Exclude<BillingPlan, "free">) =>
      action === "portal" ? openBillingPortal() : createCheckout(action),
    onSuccess: ({ url }) => window.location.assign(url),
  });
  const free = useMutation({
    mutationFn: () => changePlan("free"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["billing"] }),
  });
  const refund = useMutation({
    mutationFn: requestRefund,
    onSuccess: () => client.invalidateQueries({ queryKey: ["billing"] }),
  });
  if (billing.isLoading) return <p className="billing-state">Loading billing…</p>;
  if (billing.error) return <p className="team-error">{billing.error.message}</p>;
  const value = billing.data!;
  const currentPlan = value.subscription.plan.toLowerCase();
  const canViewInvoices = user?.role === "Owner" || user?.role === "SuperAdmin";
  const showSubscription = !subsection || subsection === "subscription";
  const showInvoices = !subsection || subsection === "invoices";
  const renewal = value.subscription.renewsAt
    ? new Date(value.subscription.renewsAt).toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : null;
  return (
    <div className="billing-management">
      {showSubscription && (
        <section className="billing-summary">
          <div className="billing-summary-icon">
            <CreditCard />
          </div>
          <div>
            <span>Current subscription</span>
            <h2>{value.subscription.plan}</h2>
            <p>
              {value.subscription.status} · {value.subscription.seats} seat(s)
              {renewal
                ? ` · ${value.subscription.status === "Canceling" ? "Access until" : "Renews"} ${renewal}`
                : ""}
            </p>
          </div>
          <div className="billing-secure">
            <ShieldCheck />
            <span>Payments securely managed by Stripe</span>
          </div>
          {value.subscription.plan !== "Free" && canViewInvoices && (
            <button onClick={() => redirect.mutate("portal")}>
              Manage billing <ExternalLink />
            </button>
          )}
        </section>
      )}

      {showSubscription && (
        <>
          <div className="billing-section-heading">
            <div>
              <span>Simple, transparent pricing</span>
              <h3>Choose the plan that matches your momentum</h3>
              <p>
                Upgrade as your content operation grows. Paid plans renew monthly and are billed securely
                through Stripe.
              </p>
            </div>
          </div>
          <div className="billing-plan-grid">
            {plans.map((plan) => {
              const current = currentPlan === plan.id;
              return (
                <article key={plan.id} className={plan.recommended ? "recommended" : ""}>
                  {plan.recommended && (
                    <div className="billing-plan-badge">
                      <Sparkles /> Most popular
                    </div>
                  )}
                  <div className="billing-plan-title">
                    <h4>{plan.name}</h4>
                    {current && <span>Current plan</span>}
                  </div>
                  <p>{plan.description}</p>
                  <div className="billing-price">
                    <strong>${plan.price.toLocaleString()}</strong>
                    <span>
                      USD
                      <br />
                      per month
                    </span>
                  </div>
                  <ul>
                    {plan.features.map((feature) => (
                      <li key={feature}>
                        <Check />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <button
                    disabled={current || redirect.isPending || free.isPending}
                    onClick={() => (plan.id === "free" ? free.mutate() : redirect.mutate(plan.id))}
                  >
                    {current
                      ? "Your current plan"
                      : plan.id === "free"
                        ? "Downgrade to Free"
                        : `Choose ${plan.name}`}
                  </button>
                </article>
              );
            })}
          </div>
        </>
      )}
      {(redirect.error || free.error) && (
        <p className="team-error billing-error">{(redirect.error ?? free.error)?.message}</p>
      )}

      {canViewInvoices && showInvoices && (
        <section className="billing-invoices">
          <div>
            <div>
              <span>Billing history</span>
              <h3>Invoices</h3>
            </div>
            <button onClick={() => redirect.mutate("portal")}>
              Payment methods & portal <ExternalLink />
            </button>
          </div>
          {value.invoices.length === 0 && (
            <div className="billing-empty">
              <CreditCard />
              <strong>No invoices yet</strong>
              <p>Your Stripe invoices will appear here after your first successful payment.</p>
            </div>
          )}
          <div className="member-list">
            {value.invoices.map((invoice) => (
              <div key={invoice.id}>
                <span>{invoice.currency.toUpperCase()}</span>
                <div>
                  <strong>{invoice.number}</strong>
                  <small>
                    {new Date(invoice.issuedAt).toLocaleDateString()} ·{" "}
                    {(invoice.amountCents / 100).toFixed(2)} {invoice.currency.toUpperCase()}
                  </small>
                </div>
                <em>{invoice.status}</em>
                {invoice.hostedUrl && (
                  <a href={invoice.hostedUrl} target="_blank" rel="noreferrer">
                    View <ExternalLink />
                  </a>
                )}
                {invoice.status === "Paid" && (
                  <button disabled={refund.isPending} onClick={() => refund.mutate(invoice.id)}>
                    Request refund
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      {subsection === "payment-methods" && canViewInvoices && (
        <section className="billing-invoices">
          <div>
            <div>
              <span>Stripe customer portal</span>
              <h3>Payment methods</h3>
              <p>Add, replace, or remove payment methods securely in Stripe.</p>
            </div>
            <button onClick={() => redirect.mutate("portal")}>
              Open secure portal <ExternalLink />
            </button>
          </div>
        </section>
      )}
      {refund.error && <p className="team-error billing-error">{refund.error.message}</p>}
    </div>
  );
}
