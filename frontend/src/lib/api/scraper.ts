import { request } from "./client";
import type { CreateScraperJobRequest, ProductView, ScraperJob } from "@/types";
export const getScraperJobs = () =>
  request<{ view: ProductView; items: ScraperJob[] }>({ url: "/scraper/jobs", method: "GET" });
export const createScraperJob = (data: CreateScraperJobRequest) =>
  request<ScraperJob>({ url: "/scraper/jobs", method: "POST", data });
