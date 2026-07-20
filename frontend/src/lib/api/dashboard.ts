import { request } from "./client";
import type { ProductView } from "@/types";

type DashboardAggregate = {
  data: Record<string, unknown>;
  degraded_services: string[];
};

export const getDashboard = async (): Promise<ProductView> => {
  const aggregate = await request<DashboardAggregate>({ url: "/dashboard/overview", method: "GET" });
  return {
    title: "Workspace overview",
    eyebrow: "Dashboard",
    description: aggregate.degraded_services.length
      ? `Live workspace data loaded with ${aggregate.degraded_services.length} service${aggregate.degraded_services.length === 1 ? "" : "s"} still unavailable.`
      : "Your connected workspace services are healthy.",
    action: "Create content",
    rows: aggregate.degraded_services.map((service) => ({
      title: `${service[0]?.toUpperCase()}${service.slice(1)} service`,
      detail: "This service has not returned dashboard data yet.",
      status: "Unavailable",
    })),
  };
};
