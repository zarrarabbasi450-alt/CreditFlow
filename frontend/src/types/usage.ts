import type { ChartPoint, Metric, ProductView } from "./api";
export interface UsageSummary {
  accountId: string;
  periodStart: string;
  periodEnd: string;
  tokensUsed: number;
  creditsUsed: number;
  modelCostCents: number;
  quotaTokens: number;
  metrics: Metric[];
  daily: ChartPoint[];
  view: ProductView;
}
