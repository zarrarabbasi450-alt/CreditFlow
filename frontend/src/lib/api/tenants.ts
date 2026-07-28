import { request } from "./client";
import type {
  Account,
  AccountInvitation,
  AccountMember,
  AccountRole,
  AccountType,
  ProductView,
  Tenant,
  Workspace,
} from "@/types";

export const listAccounts = () => request<Account[]>({ url: "/accounts/my", method: "GET" });
export const getAccount = (accountId: string) =>
  request<Account>({ url: `/accounts/${accountId}`, method: "GET" });
export const updateAccount = (accountId: string, name: string) =>
  request<Account>({ url: `/accounts/${accountId}`, method: "PATCH", data: { name } });
export const createAccount = (data: {
  name: string;
  slug: string;
  type: AccountType;
  plan_tier?: string;
  seat_count?: number;
}) => request<Account>({ url: "/accounts", method: "POST", data });
export const listAccountMembers = (accountId: string) =>
  request<AccountMember[]>({ url: `/accounts/${accountId}/members`, method: "GET" });
export const listAccountInvites = (accountId: string) =>
  request<AccountInvitation[]>({ url: `/accounts/${accountId}/invites`, method: "GET" });
export const updateAccountMemberRole = (accountId: string, userId: string, role: AccountRole) =>
  request<AccountMember>({
    url: `/accounts/${accountId}/members/${userId}`,
    method: "PATCH",
    data: { role },
  });
export const removeAccountMember = (accountId: string, userId: string) =>
  request<void>({ url: `/accounts/${accountId}/members/${userId}`, method: "DELETE" });
export const acceptInvite = (token: string) =>
  request<AccountMember>({ url: `/invites/${token}/accept`, method: "POST" });

const selectedAccountKey = "creditflow_selected_account";
export const selectedAccountStore = {
  get: () => (typeof window === "undefined" ? null : localStorage.getItem(selectedAccountKey)),
  set: (accountId: string) => localStorage.setItem(selectedAccountKey, accountId),
  clear: () => localStorage.removeItem(selectedAccountKey),
};

export const getCurrentAccount = async () => {
  const accounts = await listAccounts();
  const selectedId = selectedAccountStore.get();
  const account = accounts.find(({ id }) => id === selectedId) ?? accounts[0];
  if (!account) throw new Error("No account is available for this user");
  if (account.id !== selectedId) selectedAccountStore.set(account.id);
  return account;
};
const toTenant = (account: Account): Tenant => ({
  id: account.id,
  name: account.name,
  slug: account.slug,
  timezone: "UTC",
  locale: "en-US",
  ownerId: "",
});
const toWorkspace = (account: Account): Workspace => ({
  id: account.id,
  tenantId: account.id,
  name: account.name,
  plan: account.plan_tier,
  seatLimit: account.seat_count,
});
export const getTenant = async () => toTenant(await getCurrentAccount());
export const getWorkspace = async () => toWorkspace(await getCurrentAccount());
export const getTenantOverview = async (): Promise<{
  view: ProductView;
  tenant: Tenant;
  workspace: Workspace;
}> => {
  const account = await getCurrentAccount();
  return {
    tenant: toTenant(account),
    workspace: toWorkspace(account),
    view: {
      title: `${account.name} settings`,
      eyebrow: "Account",
      description: "Manage your account profile, plan, seats, and team access.",
      action: "Save changes",
      rows: [
        { title: "Account profile", detail: `${account.type} · ${account.slug}`, status: account.status },
        { title: "Plan", detail: `${account.seat_count} seats`, status: account.plan_tier },
      ],
    },
  };
};
