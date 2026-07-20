import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createScraperJob, getScraperJobs } from "@/lib/api/scraper";
export const useScraper = () => useQuery({ queryKey: ["scraper"], queryFn: getScraperJobs });
export function useCreateScraperJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createScraperJob,
    onSuccess: () => client.invalidateQueries({ queryKey: ["scraper"] }),
  });
}
