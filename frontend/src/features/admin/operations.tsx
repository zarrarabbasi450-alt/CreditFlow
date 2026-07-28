"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Flag, LogOut, Search, Server, Users } from "lucide-react";
import { AdminUserManagement } from "@/features/admin/user-management";
import { useToast } from "@/components/toast";
import { ConfirmDialog } from "@/components/confirm-dialog";
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

function AccountSummaryRow({ accountId }: { accountId: string }) {
  const summary = useQuery({
    queryKey: ["admin-account-summary", accountId],
    queryFn: () => adminApi.getAccountSummary(accountId),
  });
  if (summary.isLoading) return <p className="admin-summary-row">Loading summary…</p>;
  if (summary.error || !summary.data)
    return <p className="admin-summary-row">Unable to load this account&apos;s summary.</p>;
  const data = summary.data;
  return (
    <div className="admin-summary-row">
      <span>Plan: {data.plan_tier ?? "unknown"}</span>
      <span>Members: {data.member_count ?? "—"}</span>
      <span>Seats: {data.seat_count ?? "—"}</span>
      <span>Credit balance: {data.credit_balance ?? "—"}</span>
      <span>
        Usage: {data.usage_tokens ?? "—"} / {data.usage_quota_tokens ?? "—"} tokens
      </span>
    </div>
  );
}

function AdminSessionsPanel() {
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [pendingRevoke, setPendingRevoke] = useState<string | null>(null);
  const [accountFilter, setAccountFilter] = useState("");
  const appliedFilter = accountFilter.trim() || undefined;
  const sessions = useQuery({
    queryKey: ["admin-sessions", appliedFilter],
    queryFn: () => adminApi.listSessions(appliedFilter),
  });
  const revoke = useMutation({
    mutationFn: adminApi.revokeSession,
    onSuccess: () => {
      notify("Session revoked");
      setPendingRevoke(null);
      void queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
    },
    onError: (error) => notify(error instanceof Error ? error.message : "Unable to revoke session"),
  });

  return (
    <div className="admin-accounts">
      <div className="admin-accounts-filters">
        <div className="admin-accounts-search">
          <Search />
          <input
            type="search"
            placeholder="Filter by account ID…"
            value={accountFilter}
            onChange={(event) => setAccountFilter(event.target.value)}
            aria-label="Filter sessions by account"
          />
        </div>
      </div>
      {sessions.isLoading && <div className="admin-empty">Loading sessions…</div>}
      {sessions.error && (
        <EmptyState title="Unable to load sessions" detail="Auth Service rejected the request." />
      )}
      {!sessions.isLoading && !sessions.error && !sessions.data?.length && (
        <EmptyState
          title="No active sessions"
          detail={appliedFilter ? "No sessions match that account." : "No one currently holds a live session."}
        />
      )}
      {!!sessions.data?.length && (
        <div className="data-rows">
          {sessions.data.map((session) => (
            <div key={session.jti}>
              <span className="row-icon">
                <Users />
              </span>
              <div>
                <strong>{session.account_role}</strong>
                <small>
                  user {session.user_id} · account {session.account_id}
                </small>
              </div>
              <button
                className="secondary-button"
                type="button"
                disabled={revoke.isPending}
                onClick={() => setPendingRevoke(session.jti)}
              >
                <LogOut />
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={pendingRevoke !== null}
        title="Revoke this session?"
        description="The user will be signed out immediately and must log in again to continue."
        confirmLabel="Revoke session"
        busy={revoke.isPending}
        onCancel={() => setPendingRevoke(null)}
        onConfirm={() => {
          if (pendingRevoke) revoke.mutate(pendingRevoke);
        }}
      />
    </div>
  );
}

export function AdminOperations({ subsection }: { subsection?: string }) {
  const page = subsection ?? "overview";
  const [expandedAccountId, setExpandedAccountId] = useState<string | null>(null);
  const [accountSearch, setAccountSearch] = useState("");
  const [accountTypeFilter, setAccountTypeFilter] = useState<"all" | "individual" | "team">("all");
  const [accountStatusFilter, setAccountStatusFilter] = useState("all");
  const [auditAccountFilter, setAuditAccountFilter] = useState("");
  const [auditSearch, setAuditSearch] = useState("");
  const appliedAuditAccountFilter = auditAccountFilter.trim() || undefined;
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: adminApi.getAdminOverview });
  const accounts = useQuery({
    queryKey: ["admin-accounts"],
    queryFn: adminApi.listAccounts,
    enabled: page === "accounts",
  });
  const audit = useQuery({
    queryKey: ["admin-audit", appliedAuditAccountFilter],
    queryFn: () => adminApi.listAudit(appliedAuditAccountFilter),
    enabled: page === "audit",
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
  if (page === "sessions") return <AdminSessionsPanel />;
  if (page === "accounts") {
    if (accounts.isLoading) return <div className="admin-empty">Loading accounts…</div>;
    if (accounts.error)
      return <EmptyState title="Unable to load accounts" detail="Tenant Service rejected the request." />;
    if (!accounts.data?.length)
      return <EmptyState title="No accounts" detail="No tenant accounts have been created yet." />;
    const statuses = Array.from(new Set(accounts.data.map((account) => account.status))).sort();
    const query = accountSearch.trim().toLowerCase();
    const filtered = accounts.data.filter((account) => {
      const matchesQuery =
        !query || account.name.toLowerCase().includes(query) || account.slug.toLowerCase().includes(query);
      const matchesType = accountTypeFilter === "all" || account.type === accountTypeFilter;
      const matchesStatus = accountStatusFilter === "all" || account.status === accountStatusFilter;
      return matchesQuery && matchesType && matchesStatus;
    });
    return (
      <div className="admin-accounts">
        <div className="admin-accounts-filters">
          <div className="admin-accounts-search">
            <Search />
            <input
              type="search"
              placeholder="Search by name or slug…"
              value={accountSearch}
              onChange={(event) => setAccountSearch(event.target.value)}
              aria-label="Search accounts"
            />
          </div>
          <select
            value={accountTypeFilter}
            onChange={(event) => setAccountTypeFilter(event.target.value as typeof accountTypeFilter)}
            aria-label="Filter by account type"
          >
            <option value="all">All types</option>
            <option value="individual">Individual</option>
            <option value="team">Team</option>
          </select>
          <select
            value={accountStatusFilter}
            onChange={(event) => setAccountStatusFilter(event.target.value)}
            aria-label="Filter by status"
          >
            <option value="all">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
        {!filtered.length && (
          <EmptyState title="No matching accounts" detail="Try a different search term or filter." />
        )}
        {filtered.length > 0 && (
          <div className="data-rows">
            {filtered.map((account) => (
              <div key={account.id} className="admin-account-row">
                <button
                  type="button"
                  className="admin-account-row-trigger"
                  onClick={() => setExpandedAccountId(expandedAccountId === account.id ? null : account.id)}
                >
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
                </button>
                {expandedAccountId === account.id && <AccountSummaryRow accountId={account.id} />}
              </div>
            ))}
          </div>
        )}
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
  if (page === "audit") {
    const query = auditSearch.trim().toLowerCase();
    const filteredAudit = (audit.data ?? []).filter(
      (event) =>
        !query ||
        event.action.toLowerCase().includes(query) ||
        event.resource.toLowerCase().includes(query) ||
        (event.correlationId ?? "").toLowerCase().includes(query),
    );
    return (
      <div className="admin-accounts">
        <div className="admin-accounts-filters">
          <div className="admin-accounts-search">
            <Search />
            <input
              type="search"
              placeholder="Search by action, resource, or correlation ID…"
              value={auditSearch}
              onChange={(event) => setAuditSearch(event.target.value)}
              aria-label="Search audit events"
            />
          </div>
          <div className="admin-accounts-search">
            <Search />
            <input
              type="search"
              placeholder="Filter by account ID…"
              value={auditAccountFilter}
              onChange={(event) => setAuditAccountFilter(event.target.value)}
              aria-label="Filter audit events by account"
            />
          </div>
        </div>
        {audit.isLoading && <div className="admin-empty">Loading audit trail…</div>}
        {audit.error && (
          <EmptyState title="Unable to load audit trail" detail="Admin Service rejected the request." />
        )}
        {!audit.isLoading && !audit.error && !filteredAudit.length && (
          <EmptyState
            title="No audit events"
            detail={
              query || appliedAuditAccountFilter
                ? "No events match your search or filter."
                : "No platform audit events have been recorded."
            }
          />
        )}
        {!!filteredAudit.length && (
          <div className="data-rows">
            {filteredAudit.map((event) => (
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
        )}
      </div>
    );
  }
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
