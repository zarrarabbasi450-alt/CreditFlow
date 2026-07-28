import { request } from "./client";
import type {
  AdminAccount,
  AdminAccountSummary,
  AdminOverview,
  AdminSession,
  AdminUser,
  AuditEvent,
  FeatureFlag,
} from "@/types";
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
export const listSessions = (accountId?: string) =>
  request<AdminSession[]>({
    url: "/admin/sessions",
    method: "GET",
    params: accountId ? { account_id: accountId } : undefined,
  });
export const revokeSession = (jti: string) =>
  request<void>({ url: `/admin/sessions/${jti}`, method: "DELETE" });
export const getAccountSummary = (accountId: string) =>
  request<AdminAccountSummary>({ url: `/admin/accounts/${accountId}/summary`, method: "GET" });
export const listAudit = (accountId?: string) =>
  request<AuditEvent[]>({
    url: "/admin/audit",
    method: "GET",
    params: accountId ? { account_id: accountId } : undefined,
  });
