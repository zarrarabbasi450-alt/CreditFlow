import { request } from "./client";
import { getCurrentAccount, listAccountMembers } from "./tenants";
import type {
  AccountInvitation,
  AccountMember,
  AccountRole,
  Invitation,
  Paginated,
  ProductView,
  Role,
  User,
} from "@/types";

const toAccountRole = (role: Role): AccountRole => {
  if (role === "SuperAdmin") throw new Error("SuperAdmin is not an account role");
  return role.toLowerCase() as AccountRole;
};
const toRole = (role: AccountRole): Role =>
  ({ owner: "Owner", admin: "Admin", member: "Member" })[role] as Role;
const toUser = (member: AccountMember): User => ({
  id: member.user_id,
  accountId: member.account_id,
  name: member.user_id,
  email: "",
  role: toRole(member.role),
  status: "Active",
});
export const listUsers = async (page = 1): Promise<{ view: ProductView; users: Paginated<User> }> => {
  const account = await getCurrentAccount();
  const members = (await listAccountMembers(account.id)).map(toUser);
  return {
    view: {
      title: "Team & access",
      eyebrow: account.name,
      description: "Invite collaborators and manage Owner, Admin, and Member permissions.",
      action: "Invite member",
      rows: members.map((member) => ({
        title: member.name,
        detail: member.id,
        status: `${member.role} · ${member.status}`,
      })),
    },
    users: { items: members, page, pageSize: members.length || 20, total: members.length },
  };
};

export const inviteUser = async (email: string, role: Role): Promise<Invitation> => {
  const account = await getCurrentAccount();
  const invitation = await request<AccountInvitation>({
    url: `/accounts/${account.id}/invite`,
    method: "POST",
    data: { email, role: toAccountRole(role) },
  });
  return {
    id: invitation.id,
    email: invitation.email,
    role: toRole(invitation.role),
    expiresAt: invitation.expires_at,
    status: "Pending",
  };
};

export const updateUserRole = async (userId: string, role: Role): Promise<User> => {
  const account = await getCurrentAccount();
  const member = await request<AccountMember>({
    url: `/accounts/${account.id}/members/${userId}`,
    method: "PATCH",
    data: { role: toAccountRole(role) },
  });
  return toUser(member);
};

export const removeUser = async (userId: string): Promise<void> => {
  const account = await getCurrentAccount();
  await request<void>({
    url: `/accounts/${account.id}/members/${userId}`,
    method: "DELETE",
  });
};

export const acceptInvitation = (token: string) =>
  request<AccountMember>({ url: `/invites/${encodeURIComponent(token)}/accept`, method: "POST" });
