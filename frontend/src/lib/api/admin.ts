import { request } from "./client";
import type { AdminAccount, AdminOverview, AdminUser, FeatureFlag } from "@/types";
export const getAdminOverview = () =>
  request<AdminOverview>({
    url: "/admin/overview",
    method: "GET",
  });
export const updateFeatureFlag = (key: string, enabled: boolean) =>
  request<FeatureFlag>({ url: `/admin/feature-flags/${key}`, method: "PATCH", data: { enabled } });
export const listUsers = () => request<AdminUser[]>({ url: "/auth/admin/users", method: "GET" });
export const listAccounts = () => request<AdminAccount[]>({ url: "/accounts", method: "GET" });
export const updatePlatformRole = (userId: string, platformRole: "SuperAdmin" | null) =>
  request<AdminUser>({
    url: `/auth/admin/users/${userId}/platform-role`,
    method: "PATCH",
    data: { platformRole },
  });
