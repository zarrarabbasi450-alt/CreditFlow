export type Role = "Owner" | "Admin" | "Member" | "SuperAdmin";
export type Permission =
  | "workspace:read"
  | "workspace:manage"
  | "billing:read"
  | "billing:manage"
  | "content:write"
  | "admin:read"
  | "admin:manage";
export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
}
export interface WorkspaceSummary {
  id: string;
  name: string;
  tenantId: string;
  plan: string;
}
export interface AuthUser {
  id: string;
  name: string;
  email: string;
  accountId: string;
  role: Role;
  accountRole?: Exclude<Role, "SuperAdmin">;
  platformRole?: "SuperAdmin" | null;
  permissions: Permission[];
  tenant?: TenantSummary;
  workspace?: WorkspaceSummary;
}
export interface AuthTokens {
  accessToken: string;
  expiresIn: number;
}
export interface AuthSession {
  user: AuthUser;
  tokens: AuthTokens;
}
export interface LoginRequest {
  email: string;
  password: string;
}
export interface SignupRequest {
  email: string;
  password: string;
}
