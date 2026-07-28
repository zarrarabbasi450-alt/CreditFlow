"use client";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "@/lib/api/auth";
import { tokenStore } from "@/lib/api/client";
import type { AuthSession, AuthUser, Permission, TenantSummary, WorkspaceSummary } from "@/types";
type Auth = {
  user: AuthUser | null;
  permissions: Permission[];
  tenant: TenantSummary | null;
  workspace: WorkspaceSummary | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  switchAccount: (accountId: string) => Promise<void>;
};
const Context = createContext<Auth | null>(null);
let hydrationPromise: Promise<AuthSession | null> | null = null;

// The access token lives in memory only, so a hard reload always starts with none.
// The httpOnly refresh-token cookie (set by the gateway) is what survives — this
// exchanges it for a fresh access token and the current user, or fails silently
// (session cookie missing/expired) leaving the visitor logged out.
function hydrateSession(): Promise<AuthSession | null> {
  hydrationPromise ??= (async () => {
    try {
      const fresh = await authApi.refreshSession();
      tokenStore.set(fresh.tokens);
      return fresh;
    } catch {
      tokenStore.clear();
      return null;
    }
  })();
  return hydrationPromise;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    const hydrate = async () => {
      try {
        const fresh = await hydrateSession();
        if (active) setSession(fresh);
      } finally {
        if (active) setReady(true);
      }
    };
    void hydrate();
    return () => {
      active = false;
    };
  }, []);
  const persist = (next: AuthSession | null) => {
    hydrationPromise = Promise.resolve(next);
    setSession(next);
    if (next) tokenStore.set(next.tokens);
    else tokenStore.clear();
  };
  const value = useMemo<Auth>(
    () => ({
      user: session?.user ?? null,
      permissions: session?.user.permissions ?? [],
      tenant: session?.user.tenant ?? null,
      workspace: session?.user.workspace ?? null,
      ready,
      login: async (email, password) => {
        const next = await authApi.login({ email, password });
        persist(next);
        return next.user;
      },
      signup: async (email, password) => {
        await authApi.signup({ email, password });
        const next = await authApi.login({ email, password });
        persist(next);
        return next.user;
      },
      logout: async () => {
        try {
          if (session) await authApi.logout();
        } finally {
          persist(null);
        }
      },
      refresh: async () => {
        if (!session) return;
        persist(await authApi.refreshSession());
      },
      switchAccount: async (accountId) => persist(await authApi.switchAccount(accountId)),
    }),
    [session, ready],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
