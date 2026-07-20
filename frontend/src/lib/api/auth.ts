import { request } from "./client";
import type {
  AuthSession,
  AuthTokens,
  AuthUser,
  LoginRequest,
  Permission,
  Role,
  SignupRequest,
} from "@/types";

type BackendAuthUser = {
  id: string;
  email: string;
  accountId: string;
  role: Role;
  accountRole: Exclude<Role, "SuperAdmin">;
  platformRole: "SuperAdmin" | null;
};
type BackendAuthSession = { user: BackendAuthUser; tokens: AuthTokens };

const permissions: Record<Role, Permission[]> = {
  Owner: ["workspace:read", "workspace:manage", "billing:read", "billing:manage", "content:write"],
  Admin: ["workspace:read", "workspace:manage", "billing:read", "content:write"],
  Member: ["workspace:read", "content:write"],
  SuperAdmin: ["workspace:read", "admin:read", "admin:manage"],
};

const toUser = (value: BackendAuthUser): AuthUser => ({
  id: value.id,
  name: value.email.split("@", 1)[0],
  email: value.email,
  role: value.role,
  accountRole: value.accountRole,
  platformRole: value.platformRole,
  permissions: permissions[value.role],
});

export const signup = (data: SignupRequest) =>
  request<BackendAuthUser>({ url: "/auth/signup", method: "POST", data });
export const login = async (data: LoginRequest): Promise<AuthSession> => {
  const session = await request<BackendAuthSession>({ url: "/auth/login", method: "POST", data });
  return { user: toUser(session.user), tokens: session.tokens };
};
export const logout = (refreshToken: string) =>
  request<void>({ url: "/auth/logout", method: "POST", data: { refreshToken } });
export const refreshToken = async (refreshToken: string) =>
  (await request<BackendAuthSession>({ url: "/auth/refresh", method: "POST", data: { refreshToken } }))
    .tokens;
export const switchAccount = async (accountId: string): Promise<AuthSession> => {
  const session = await request<BackendAuthSession>({
    url: "/auth/switch-account",
    method: "POST",
    data: { accountId },
  });
  return { user: toUser(session.user), tokens: session.tokens };
};
export const getCurrentUser = () => request<AuthSession["user"]>({ url: "/auth/me", method: "GET" });
