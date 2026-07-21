import type { ChartPoint, Metric, ProductView } from "./api";

export interface ModelUsage {
  model: string;
  tokens: number;
  costMicrousd: number;
  generations: number;
}

export interface UsageLedgerEntry {
  id: string;
  eventId: string;
  generationId: string;
  accountId: string;
  userId: string;
  model: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costMicrousd: number;
  createdAt: string;
}

export interface UsageSummary {
  accountId: string;
  periodStart: string;
  periodEnd: string;
  tokensUsed: number;
  costMicrousd: number;
  quotaTokens: number;
  remainingTokens: number;
  quotaPercentage: number;
  generations: number;
  byModel: ModelUsage[];
  metrics: Metric[];
  daily: ChartPoint[];
  view: ProductView;
}
