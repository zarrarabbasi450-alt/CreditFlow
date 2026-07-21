"use client";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cancelCreditPurchase,
  cancelCreditListing,
  confirmCreditPurchase,
  createCreditListing,
  getCredits,
  purchaseCredits,
} from "@/lib/api/credits";
import { useAuth } from "@/hooks/useAuth";

const publishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "";
const stripePromise = publishableKey ? loadStripe(publishableKey) : null;
type Payment = { listingId: string; paymentIntentId: string; clientSecret: string };

function PaymentForm({ payment, close }: { payment: Payment; close: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const cancel = async () => {
    await cancelCreditPurchase(payment.listingId);
    close();
    await client.invalidateQueries({ queryKey: ["credits"] });
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!stripe || !elements) return;
    setSubmitting(true);
    setError("");
    const result = await stripe.confirmPayment({ elements, redirect: "if_required" });
    if (result.error) {
      setError(result.error.message ?? "Stripe could not authorize the payment");
      setSubmitting(false);
      return;
    }
    try {
      await confirmCreditPurchase(payment.listingId, payment.paymentIntentId);
      close();
      await client.invalidateQueries({ queryKey: ["credits"] });
    } catch (value) {
      setError(value instanceof Error ? value.message : "Credit transfer failed");
      setSubmitting(false);
    }
  };
  return (
    <div className="credits-payment">
      <form onSubmit={submit}>
        <h3>Secure marketplace payment</h3>
        <PaymentElement />
        <button className="primary-button" disabled={!stripe || submitting}>
          {submitting ? "Processing…" : "Pay and receive credits"}
        </button>
        <button type="button" onClick={() => void cancel()}>
          Cancel
        </button>
        {error && <p className="team-error">{error}</p>}
      </form>
    </div>
  );
}

export function CreditsManagement({ subsection }: { subsection?: string }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const overview = useQuery({ queryKey: ["credits"], queryFn: getCredits });
  const [credits, setCredits] = useState("");
  const [price, setPrice] = useState("");
  const [payment, setPayment] = useState<Payment | null>(null);
  const [configurationError, setConfigurationError] = useState("");
  const create = useMutation({
    mutationFn: createCreditListing,
    onSuccess: () => {
      setCredits("");
      setPrice("");
      void client.invalidateQueries({ queryKey: ["credits"] });
    },
  });
  const cancelListing = useMutation({
    mutationFn: cancelCreditListing,
    onSuccess: () => client.invalidateQueries({ queryKey: ["credits"] }),
  });
  const purchase = useMutation({
    mutationFn: purchaseCredits,
    onSuccess: (value, listingId) => {
      if (!value.client_secret || !publishableKey) {
        void cancelCreditPurchase(listingId);
        setConfigurationError("Stripe publishable key is not configured");
        void client.invalidateQueries({ queryKey: ["credits"] });
        return;
      }
      setPayment({ listingId, paymentIntentId: value.payment_intent_id, clientSecret: value.client_secret });
    },
  });
  if (overview.isLoading) return <p>Loading credits…</p>;
  if (overview.error) return <p className="team-error">{overview.error.message}</p>;
  const value = overview.data!;
  const showMarketplace = !subsection || subsection === "marketplace";
  const showLedger = !subsection || subsection === "ledger";
  return (
    <div className="credits-management">
      <div className="metric-grid">
        <article>
          <div>
            <span>Available credits</span>
          </div>
          <strong>{value.balance.toLocaleString()}</strong>
          <small>Derived from the ledger</small>
        </article>
        <article>
          <div>
            <span>Open marketplace offers</span>
          </div>
          <strong>{value.listings.length}</strong>
          <small>Secure Billing escrow</small>
        </article>
      </div>
      {showMarketplace && (
        <form
          className="generator"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate({ credits: Number(credits), priceCents: Math.round(Number(price) * 100) });
          }}
        >
          <label htmlFor="listing-credits">List surplus credits</label>
          <input
            id="listing-credits"
            type="number"
            min="1"
            required
            placeholder="Credits"
            value={credits}
            onChange={(event) => setCredits(event.target.value)}
          />
          <label htmlFor="listing-price">Price (USD)</label>
          <input
            id="listing-price"
            type="number"
            min="0.01"
            step="0.01"
            required
            placeholder="Price"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
          <button className="primary-button" disabled={create.isPending}>
            Create listing
          </button>
          {create.error && <p className="team-error">{create.error.message}</p>}
        </form>
      )}
      {showMarketplace && (
        <div className="data-rows">
          {value.listings.map((item) => (
            <div key={item.id}>
              <div>
                <strong>{item.credits.toLocaleString()} credits</strong>
                <small>
                  ${(item.priceCents / 100).toFixed(2)} · expires{" "}
                  {new Date(item.expiresAt).toLocaleDateString()}
                </small>
              </div>
              {item.sellerAccountId !== user?.workspace?.id && (
                <button
                  className="primary-button"
                  disabled={purchase.isPending}
                  onClick={() => purchase.mutate(item.id)}
                >
                  Buy
                </button>
              )}
              {item.sellerAccountId === user?.workspace?.id && (
                <button disabled={cancelListing.isPending} onClick={() => cancelListing.mutate(item.id)}>
                  Cancel listing
                </button>
              )}
            </div>
          ))}
          {!value.listings.length && <p>No marketplace listings are currently available.</p>}
        </div>
      )}
      {configurationError && <p className="team-error">{configurationError}</p>}
      {purchase.error && <p className="team-error">{purchase.error.message}</p>}
      {showMarketplace && payment && stripePromise && (
        <Elements stripe={stripePromise} options={{ clientSecret: payment.clientSecret }}>
          <PaymentForm payment={payment} close={() => setPayment(null)} />
        </Elements>
      )}
      {showLedger && (
        <div className="data-rows">
          {value.ledger.map((entry) => (
            <div key={entry.id}>
              <div>
                <strong>{entry.description}</strong>
                <small>
                  {new Date(entry.createdAt).toLocaleString()} · {entry.type}
                </small>
              </div>
              <em>
                {entry.amount > 0 ? "+" : ""}
                {entry.amount.toLocaleString()}
              </em>
            </div>
          ))}
          {!value.ledger.length && <p>No credit transactions have been recorded.</p>}
        </div>
      )}
      {cancelListing.error && <p className="team-error">{cancelListing.error.message}</p>}
    </div>
  );
}
