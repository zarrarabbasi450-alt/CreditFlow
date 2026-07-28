import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelScraperJob,
  createScraperJob,
  getScraperJob,
  getScraperJobDocuments,
  getScraperJobs,
} from "@/lib/api/scraper";
import type { CreateScraperJobRequest } from "@/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export const useScraper = () => useQuery({ queryKey: ["scraper"], queryFn: getScraperJobs });

export const useScraperJobDocuments = (jobId: string | null) =>
  useQuery({
    queryKey: ["scraper", "documents", jobId],
    queryFn: () => getScraperJobDocuments(jobId as string),
    enabled: Boolean(jobId),
  });

/** Polls a single job until it reaches a terminal status (used to watch a
 * just-created search/scrape job go from queued/running to its final answer). */
export const useScraperJobStatus = (jobId: string | null) =>
  useQuery({
    queryKey: ["scraper", "job", jobId],
    queryFn: () => getScraperJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (query.state.data && TERMINAL_STATUSES.has(query.state.data.status) ? false : 1200),
  });

export function useScraperMutations() {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["scraper"] }),
      queryClient.invalidateQueries({ queryKey: ["product-view", "scraper"] }),
    ]);
  };
  return {
    create: useMutation({
      mutationFn: (payload: CreateScraperJobRequest) => createScraperJob(payload),
      onSuccess: refresh,
    }),
    cancel: useMutation({ mutationFn: (jobId: string) => cancelScraperJob(jobId), onSuccess: refresh }),
  };
}
