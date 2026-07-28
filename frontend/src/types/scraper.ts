export type ScraperJobType = "url" | "serp" | "research";
export type ScraperJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface ScraperJob {
  id: string;
  accountId: string;
  createdBy: string;
  jobType: ScraperJobType;
  target: string;
  name: string;
  maxPages: number;
  status: ScraperJobStatus;
  recurring: boolean;
  intervalHours?: number | null;
  nextRunAt?: string | null;
  lastRunAt?: string | null;
  pagesProcessed: number;
  answer?: string | null;
  answerHtml?: string;
  failureReason?: string | null;
  attempts: number;
  createdAt: string;
  updatedAt: string;
}

export interface ScrapedDocument {
  id: string;
  jobId: string;
  accountId: string;
  jobType: ScraperJobType;
  source: string;
  title?: string | null;
  text: string;
  data: Record<string, unknown>;
  fetchedAt: string;
}

export interface CreateScraperJobRequest {
  jobType: ScraperJobType;
  target: string;
  name: string;
  maxPages?: number;
  recurring?: boolean;
  intervalHours?: number | null;
}
