"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Flag, Server, Users } from "lucide-react";
import { AdminUserManagement } from "@/features/admin/user-management";
import * as adminApi from "@/lib/api/admin";

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="admin-empty">
      <CheckCircle2 />
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export function AdminOperations({ subsection }: { subsection?: string }) {
  const page = subsection ?? "overview";
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: adminApi.getAdminOverview });
  const accounts = useQuery({
    queryKey: ["admin-accounts"],
    queryFn: adminApi.listAccounts,
    enabled: page === "accounts",
  });

  if (overview.isLoading) return <div className="admin-empty">Loading operations…</div>;
  if (overview.error || !overview.data)
    return (
      <EmptyState
        title="Operations data is unavailable"
        detail="Check that the API Gateway and completed backend services are running."
      />
    );
  if (page === "users") return <AdminUserManagement />;
  if (page === "accounts") {
    if (accounts.isLoading) return <div className="admin-empty">Loading accounts…</div>;
    if (accounts.error)
      return <EmptyState title="Unable to load accounts" detail="Tenant Service rejected the request." />;
    if (!accounts.data?.length)
      return <EmptyState title="No accounts" detail="No tenant accounts have been created yet." />;
    return (
      <div className="data-rows">
        {accounts.data.map((account) => (
          <div key={account.id}>
            <span className="row-icon">
              <Users />
            </span>
            <div>
              <strong>{account.name}</strong>
              <small>
                {account.type} · {account.plan_tier} · {account.seat_count} seat(s)
              </small>
            </div>
            <em>{account.status}</em>
          </div>
        ))}
      </div>
    );
  }
  if (page === "health" || page === "overview")
    return (
      <div className="data-rows">
        {overview.data.health.map((service) => (
          <div key={service.service}>
            <span className="row-icon">
              <Server />
            </span>
            <div>
              <strong>{service.service}</strong>
              <small>
                {service.detail} · {service.latencyP95Ms}ms
              </small>
            </div>
            <em>{service.status}</em>
          </div>
        ))}
      </div>
    );
  if (page === "audit")
    return overview.data.audit.length ? (
      <div className="data-rows">
        {overview.data.audit.map((event) => (
          <div key={event.id}>
            <span className="row-icon">
              <Clock3 />
            </span>
            <div>
              <strong>{event.action}</strong>
              <small>
                {event.resource} · {new Date(event.createdAt).toLocaleString()}
              </small>
            </div>
            <em>{event.correlationId}</em>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState title="No audit events" detail="No platform audit events have been recorded." />
    );
  if (page === "feature-flags")
    return overview.data.flags.length ? (
      <div className="data-rows">
        {overview.data.flags.map((flag) => (
          <div key={flag.key}>
            <span className="row-icon">
              <Flag />
            </span>
            <div>
              <strong>{flag.key}</strong>
              <small>{flag.rolloutPercentage}% rollout</small>
            </div>
            <em>{flag.enabled ? "Enabled" : "Disabled"}</em>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState title="No feature flags" detail="No platform feature flags are configured." />
    );
  return (
    <EmptyState title="No failed jobs" detail="No failed jobs have been reported by completed services." />
  );
}
