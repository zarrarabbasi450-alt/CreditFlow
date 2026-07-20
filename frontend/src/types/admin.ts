export interface ServiceHealth {
  service: string;
  status: "Healthy" | "Degraded" | "Down";
  uptime: number;
  latencyP95Ms: number;
  detail: string;
}
export interface AuditEvent {
  id: string;
  actorId: string;
  accountId?: string;
  action: string;
  resource: string;
  createdAt: string;
  correlationId: string;
}
export interface FeatureFlag {
  key: string;
  enabled: boolean;
  rolloutPercentage: number;
  updatedAt: string;
}
