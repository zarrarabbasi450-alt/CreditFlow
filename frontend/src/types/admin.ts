export interface ServiceHealth {
  service: string;
  status: "Healthy" | "Degraded" | "Down";
  uptime: number;
  latencyP95Ms: number;
  detail: string;
}
export interface AuditEvent {
  id: string;
  actorId: string | null;
  accountId?: string | null;
  action: string;
  resource: string;
  createdAt: string;
  correlationId: string | null;
}
export interface FeatureFlag {
  key: string;
  enabled: boolean;
  rolloutPercentage: number;
  updatedAt: string;
}

export interface AdminUser {
  id: string;
  email: string;
  isActive: boolean;
  isEmailVerified: boolean;
  platformRole: "SuperAdmin" | null;
}

export interface AdminAccount {
  id: string;
  name: string;
  slug: string;
  status: string;
  type: "individual" | "team";
  plan_tier: string;
  seat_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminOverview {
  view: import("./api").ProductView;
  health: ServiceHealth[];
  audit: AuditEvent[];
  flags: FeatureFlag[];
}

export interface AdminSession {
  jti: string;
  user_id: string;
  account_id: string;
  account_role: string;
  platform_role: "SuperAdmin" | null;
}

export interface AdminAccountSummary {
  account_id: string;
  plan_tier: string | null;
  seat_count: number | null;
  member_count: number | null;
  credit_balance: number | null;
  usage_tokens: number | null;
  usage_quota_tokens: number | null;
}
