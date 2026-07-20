export interface ScraperJob {
  id: string;
  accountId: string;
  url: string;
  name: string;
  status: "Queued" | "Running" | "Complete" | "Failed";
  pagesProcessed: number;
  insightCount: number;
  createdAt: string;
}
export interface CreateScraperJobRequest {
  accountId: string;
  url: string;
  name: string;
  maxPages: number;
}
