import { request } from "./client";
import type {
  CreateScraperJobRequest,
  ProductView,
  ScrapedDocument,
  ScraperJob,
  ScraperJobStatus,
  ScraperJobType,
} from "@/types";

interface RawScraperJob {
  id: string;
  account_id: string;
  created_by: string;
  job_type: ScraperJobType;
  target: string;
  name: string;
  max_pages: number;
  status: ScraperJobStatus;
  recurring: boolean;
  interval_hours?: number | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  pages_processed: number;
  answer?: string | null;
  answer_html?: string;
  failure_reason?: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
}

interface RawScrapedDocument {
  id: string;
  job_id: string;
  account_id: string;
  job_type: ScraperJobType;
  source: string;
  title?: string | null;
  text: string;
  data: Record<string, unknown>;
  fetched_at: string;
}

const toJob = (job: RawScraperJob): ScraperJob => ({
  id: job.id,
  accountId: job.account_id,
  createdBy: job.created_by,
  jobType: job.job_type,
  target: job.target,
  name: job.name,
  maxPages: job.max_pages,
  status: job.status,
  recurring: job.recurring,
  intervalHours: job.interval_hours ?? null,
  nextRunAt: job.next_run_at ?? null,
  lastRunAt: job.last_run_at ?? null,
  pagesProcessed: job.pages_processed,
  answer: job.answer ?? null,
  answerHtml: job.answer_html ?? "",
  failureReason: job.failure_reason ?? null,
  attempts: job.attempts,
  createdAt: job.created_at,
  updatedAt: job.updated_at,
});

const toDocument = (document: RawScrapedDocument): ScrapedDocument => ({
  id: document.id,
  jobId: document.job_id,
  accountId: document.account_id,
  jobType: document.job_type,
  source: document.source,
  title: document.title ?? null,
  text: document.text,
  data: document.data,
  fetchedAt: document.fetched_at,
});

const toCreatePayload = (data: CreateScraperJobRequest) => ({
  job_type: data.jobType,
  target: data.target,
  name: data.name,
  max_pages: data.maxPages ?? 1,
  recurring: data.recurring ?? false,
  interval_hours: data.intervalHours ?? null,
});

export const getScraperJobs = async (): Promise<{ view: ProductView; items: ScraperJob[] }> => {
  const response = await request<{ view: ProductView; items: RawScraperJob[] }>({
    url: "/scraper/jobs",
    method: "GET",
  });
  return { view: response.view, items: response.items.map(toJob) };
};

export const createScraperJob = (data: CreateScraperJobRequest) =>
  request<RawScraperJob>({ url: "/scraper/jobs", method: "POST", data: toCreatePayload(data) }).then(toJob);

export const getScraperJob = (jobId: string) =>
  request<RawScraperJob>({ url: `/scraper/jobs/${jobId}`, method: "GET" }).then(toJob);

export const cancelScraperJob = (jobId: string) =>
  request<RawScraperJob>({ url: `/scraper/jobs/${jobId}/cancel`, method: "POST" }).then(toJob);

export const getScraperJobDocuments = (jobId: string) =>
  request<RawScrapedDocument[]>({ url: `/scraper/jobs/${jobId}/documents`, method: "GET" }).then((items) =>
    items.map(toDocument),
  );
