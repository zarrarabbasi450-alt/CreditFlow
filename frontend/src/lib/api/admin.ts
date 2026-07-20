import { request } from "./client";
import type { AuditEvent, FeatureFlag, ProductView, ServiceHealth } from "@/types";
export const getAdminOverview = () =>
  request<{ view: ProductView; health: ServiceHealth[]; audit: AuditEvent[]; flags: FeatureFlag[] }>({
    url: "/admin/overview",
    method: "GET",
  });
export const updateFeatureFlag = (key: string, enabled: boolean) =>
  request<FeatureFlag>({ url: `/admin/feature-flags/${key}`, method: "PATCH", data: { enabled } });
