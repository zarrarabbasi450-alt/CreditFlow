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
  accountId: value.accountId,
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
export const logout = () => request<void>({ url: "/auth/logout", method: "POST", data: {} });
export const refreshSession = async (): Promise<AuthSession> => {
  const session = await request<BackendAuthSession>({ url: "/auth/refresh", method: "POST", data: {} });
  return { user: toUser(session.user), tokens: session.tokens };
};
export const switchAccount = async (accountId: string): Promise<AuthSession> => {
  const session = await request<BackendAuthSession>({
    url: "/auth/switch-account",
    method: "POST",
    data: { accountId },
  });
  return { user: toUser(session.user), tokens: session.tokens };
};
export const getCurrentUser = async (): Promise<AuthUser> =>
  toUser(await request<BackendAuthUser>({ url: "/auth/me", method: "GET" }));
export const verifyEmail = (token: string) =>
  request<{ message: string }>({ url: "/auth/verify-email", method: "POST", data: { token } });
export const requestPasswordReset = (email: string) =>
  request<{ message: string }>({ url: "/auth/forgot-password", method: "POST", data: { email } });
export const verifyResetCode = (email: string, code: string) =>
  request<{ message: string }>({
    url: "/auth/forgot-password/verify",
    method: "POST",
    data: { email, code },
  });
export const resetPassword = (email: string, code: string, password: string) =>
  request<{ message: string }>({
    url: "/auth/reset-password",
    method: "POST",
    data: { email, code, password },
  });
