import { request } from "./client";
import type { UsageLedgerEntry, UsageSummary } from "@/types";

interface ApiModelUsage {
  model: string;
  tokens: number;
  cost_microusd: number;
  generations: number;
}

interface ApiDailyUsage {
  day: string;
  tokens: number;
  cost_microusd: number;
  generations: number;
}

interface ApiUsageSummary {
  account_id: string;
  period_start: string;
  period_end: string;
  tokens_used: number;
  cost_microusd: number;
  quota_tokens: number;
  remaining_tokens: number;
  quota_percentage: number;
  generations: number;
  by_model: ApiModelUsage[];
  daily: ApiDailyUsage[];
}

interface ApiLedgerEntry {
  id: string;
  event_id: string;
  generation_id: string;
  account_id: string;
  user_id: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_microusd: number;
  created_at: string;
}

const integer = new Intl.NumberFormat("en-US");
const usd = (microusd: number) => `$${(microusd / 1_000_000).toFixed(2)}`;

export async function getUsage(): Promise<UsageSummary> {
  const data = await request<ApiUsageSummary>({ url: "/usage/summary", method: "GET" });
  const byModel = data.by_model.map((item) => ({
    model: item.model,
    tokens: item.tokens,
    costMicrousd: item.cost_microusd,
    generations: item.generations,
  }));
  const daily = data.daily.map((item) => ({
    day: item.day.slice(5),
    tokens: item.tokens,
    posts: item.generations,
  }));
  return {
    accountId: data.account_id,
    periodStart: data.period_start,
    periodEnd: data.period_end,
    tokensUsed: data.tokens_used,
    costMicrousd: data.cost_microusd,
    quotaTokens: data.quota_tokens,
    remainingTokens: data.remaining_tokens,
    quotaPercentage: data.quota_percentage,
    generations: data.generations,
    byModel,
    daily,
    metrics: [
      {
        label: "Tokens used",
        value: integer.format(data.tokens_used),
        change: `${data.quota_percentage}% of quota`,
      },
      { label: "Remaining", value: integer.format(data.remaining_tokens), change: "Live quota" },
      { label: "AI cost", value: usd(data.cost_microusd), change: "This month" },
      { label: "Generations", value: integer.format(data.generations), change: `${byModel.length} model(s)` },
    ],
    view: {
      title: "Usage & metering",
      eyebrow: "LIVE QUOTA",
      description: "Track token consumption, model cost, and generation volume for this workspace.",
      action: "Refresh usage",
      metrics: [],
      chart: daily,
      rows: byModel.map((item) => ({
        title: item.model,
        detail: `${integer.format(item.tokens)} tokens · ${item.generations} generation(s)`,
        status: usd(item.costMicrousd),
      })),
    },
  };
}

export async function getUsageLedger(): Promise<UsageLedgerEntry[]> {
  const data = await request<ApiLedgerEntry[]>({ url: "/usage/ledger", method: "GET" });
  return data.map((item) => ({
    id: item.id,
    eventId: item.event_id,
    generationId: item.generation_id,
    accountId: item.account_id,
    userId: item.user_id,
    model: item.model,
    promptTokens: item.prompt_tokens,
    completionTokens: item.completion_tokens,
    totalTokens: item.total_tokens,
    costMicrousd: item.cost_microusd,
    createdAt: item.created_at,
  }));
}
