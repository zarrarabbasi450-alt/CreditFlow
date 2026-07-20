import { useQuery } from "@tanstack/react-query";
import { getAdminOverview } from "@/lib/api/admin";
import { getBilling } from "@/lib/api/billing";
import { getAiOverview, getContent } from "@/lib/api/content";
import { getCredits } from "@/lib/api/credits";
import { getDashboard } from "@/lib/api/dashboard";
import { getNotifications } from "@/lib/api/notifications";
import { getPublishing } from "@/lib/api/publishing";
import { getSchedules } from "@/lib/api/scheduler";
import { getScraperJobs } from "@/lib/api/scraper";
import { getTenantOverview } from "@/lib/api/tenants";
import { getUsage } from "@/lib/api/usage";
import { listUsers } from "@/lib/api/users";
import type { ProductView } from "@/types";
const loaders: Record<string, () => Promise<ProductView>> = {
  dashboard: getDashboard,
  "ai-studio": getAiOverview,
  content: async () => (await getContent()).view,
  scheduler: async () => (await getSchedules()).view,
  publishing: async () => (await getPublishing()).view,
  scraper: async () => (await getScraperJobs()).view,
  usage: async () => (await getUsage()).view,
  credits: async () => (await getCredits()).view,
  billing: async () => (await getBilling()).view,
  team: async () => (await listUsers()).view,
  notifications: async () => (await getNotifications()).view,
  settings: async () => (await getTenantOverview()).view,
  admin: async () => (await getAdminOverview()).view,
};
export const useProductView = (section: string) =>
  useQuery({
    queryKey: ["product-view", section],
    queryFn: loaders[section],
    enabled: Boolean(loaders[section]),
  });
