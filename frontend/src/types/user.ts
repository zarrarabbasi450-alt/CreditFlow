import type { Role } from "./auth";
export interface User {
  id: string;
  accountId: string;
  name: string;
  email: string;
  role: Role;
  status: "Active" | "Invited" | "Suspended";
  lastActiveAt?: string;
}
export interface Tenant {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  locale: string;
  ownerId: string;
}
export interface Workspace {
  id: string;
  tenantId: string;
  name: string;
  plan: string;
  seatLimit: number;
}
export interface Invitation {
  id: string;
  email: string;
  role: Role;
  expiresAt: string;
  status: "Pending" | "Accepted" | "Expired";
}

export type AccountType = "individual" | "team";
export type AccountRole = "owner" | "admin" | "member";
export interface Account {
  id: string;
  name: string;
  slug: string;
  status: string;
  type: AccountType;
  plan_tier: string;
  seat_count: number;
  created_at: string;
  updated_at: string;
}
export interface AccountMember {
  id: string;
  account_id: string;
  user_id: string;
  role: AccountRole;
  created_at: string;
  updated_at: string;
}
export interface AccountInvitation {
  id: string;
  account_id: string;
  email: string;
  role: AccountRole;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
}
