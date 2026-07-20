"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, UserPlus } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  getCurrentAccount,
  listAccountMembers,
  removeAccountMember,
  updateAccountMemberRole,
} from "@/lib/api/tenants";
import { inviteUser } from "@/lib/api/users";
import type { AccountRole, Role } from "@/types";

const displayRole = (role: AccountRole): Role =>
  ({ owner: "Owner", admin: "Admin", member: "Member" })[role] as Role;

export function TeamManagement() {
  const { user } = useAuth();
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("Member");
  const account = useQuery({ queryKey: ["selected-account"], queryFn: getCurrentAccount });
  const members = useQuery({
    queryKey: ["account-members", account.data?.id],
    queryFn: () => listAccountMembers(account.data!.id),
    enabled: Boolean(account.data),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["account-members", account.data?.id] });
  const invite = useMutation({
    mutationFn: () => inviteUser(email, role),
    onSuccess: () => {
      setEmail("");
    },
  });
  const update = useMutation({
    mutationFn: ({ userId, nextRole }: { userId: string; nextRole: AccountRole }) =>
      updateAccountMemberRole(account.data!.id, userId, nextRole),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (userId: string) => removeAccountMember(account.data!.id, userId),
    onSuccess: refresh,
  });
  const viewerRole = user?.platformRole === "SuperAdmin" ? "SuperAdmin" : (user?.accountRole ?? user?.role);
  const canManage = viewerRole === "Owner" || viewerRole === "Admin" || viewerRole === "SuperAdmin";
  const canManageMember = (memberRole: AccountRole) =>
    viewerRole === "SuperAdmin" ||
    viewerRole === "Owner" ||
    (viewerRole === "Admin" && memberRole === "member");

  return (
    <div className="team-management">
      {canManage && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (email.trim()) invite.mutate();
          }}
        >
          <input
            id="team-invite-email"
            type="email"
            required
            placeholder="teammate@company.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <select value={role} onChange={(event) => setRole(event.target.value as Role)}>
            {viewerRole !== "Admin" && <option>Admin</option>}
            <option>Member</option>
          </select>
          <button className="primary-button" disabled={invite.isPending}>
            <UserPlus />
            Invite member
          </button>
        </form>
      )}
      {invite.isSuccess && <p className="team-feedback">Invitation created and queued for delivery.</p>}
      {invite.error && <p className="team-error">{invite.error.message}</p>}
      <div className="member-list">
        {members.isLoading && <p>Loading members…</p>}
        {members.data?.map((member) => (
          <div key={member.id}>
            <span>{member.user_id.slice(0, 2).toUpperCase()}</span>
            <div>
              <strong>{member.user_id === user?.id ? "You" : member.user_id}</strong>
              <small>Active member · {displayRole(member.role)}</small>
            </div>
            <select
              value={member.role}
              disabled={!canManageMember(member.role) || update.isPending}
              onChange={(event) =>
                update.mutate({ userId: member.user_id, nextRole: event.target.value as AccountRole })
              }
            >
              {viewerRole !== "Admin" && <option value="owner">Owner</option>}
              <option value="admin">Admin</option>
              <option value="member">Member</option>
            </select>
            <button
              aria-label={`Remove ${member.user_id}`}
              disabled={!canManageMember(member.role) || member.user_id === user?.id || remove.isPending}
              onClick={() => remove.mutate(member.user_id)}
            >
              <Trash2 />
            </button>
            <em>{displayRole(member.role)}</em>
          </div>
        ))}
      </div>
      {(members.error || update.error || remove.error) && (
        <p className="team-error">{(members.error ?? update.error ?? remove.error)?.message}</p>
      )}
    </div>
  );
}
