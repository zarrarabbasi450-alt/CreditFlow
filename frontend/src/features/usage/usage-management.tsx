"use client";

import { useUsage, useUsageLedger } from "@/hooks/useUsage";

const integer = new Intl.NumberFormat("en-US");
const usd = (microusd: number) => `$${(microusd / 1_000_000).toFixed(2)}`;

export function UsageManagement({ subsection }: { subsection?: string }) {
  const summary = useUsage();
  const ledger = useUsageLedger(subsection === "ledger");

  if (summary.isLoading) return <p>Loading metered usage…</p>;
  if (summary.error || !summary.data) return <p>Usage data could not be loaded.</p>;

  if (subsection === "ledger") {
    if (ledger.isLoading) return <p>Loading append-only ledger…</p>;
    if (ledger.error) return <p>The usage ledger could not be loaded.</p>;
    return (
      <div className="data-rows">
        {(ledger.data ?? []).length === 0 && <p>No AI generations have been metered this month.</p>}
        {(ledger.data ?? []).map((entry) => (
          <div key={entry.id}>
            <div>
              <strong>{entry.model}</strong>
              <small>
                {new Date(entry.createdAt).toLocaleString()} · {integer.format(entry.promptTokens)} prompt +{" "}
                {integer.format(entry.completionTokens)} completion
              </small>
            </div>
            <em>
              {integer.format(entry.totalTokens)} tokens · {usd(entry.costMicrousd)}
            </em>
          </div>
        ))}
      </div>
    );
  }

  if (subsection === "models") {
    return (
      <div className="data-rows">
        {summary.data.byModel.length === 0 && <p>No model usage has been recorded this month.</p>}
        {summary.data.byModel.map((model) => (
          <div key={model.model}>
            <div>
              <strong>{model.model}</strong>
              <small>{model.generations} generation(s)</small>
            </div>
            <em>
              {integer.format(model.tokens)} tokens · {usd(model.costMicrousd)}
            </em>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="data-rows">
      <div>
        <div>
          <strong>Monthly token quota</strong>
          <small>
            {integer.format(summary.data.tokensUsed)} of {integer.format(summary.data.quotaTokens)} tokens
            consumed
          </small>
        </div>
        <em>{summary.data.quotaPercentage}%</em>
      </div>
      <div>
        <div>
          <strong>Current billing period</strong>
          <small>
            {new Date(summary.data.periodStart).toLocaleDateString()} –{" "}
            {new Date(summary.data.periodEnd).toLocaleDateString()}
          </small>
        </div>
        <em>{integer.format(summary.data.remainingTokens)} remaining</em>
      </div>
    </div>
  );
}
