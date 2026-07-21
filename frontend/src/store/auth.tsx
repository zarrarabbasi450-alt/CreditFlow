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
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  switchAccount: (accountId: string) => Promise<void>;
};
const Context = createContext<Auth | null>(null);
const storageKey = "creditflow_auth_session";
let hydrationPromise: Promise<AuthSession | null> | null = null;

function hydrateSession(): Promise<AuthSession | null> {
  hydrationPromise ??= (async () => {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    try {
      const stored = JSON.parse(raw) as AuthSession;
      tokenStore.set(stored.tokens);
      const fresh = await authApi.refreshSession(stored.tokens.refreshToken);
      tokenStore.set(fresh.tokens);
      localStorage.setItem(storageKey, JSON.stringify(fresh));
      return fresh;
    } catch {
      tokenStore.clear();
      localStorage.removeItem(storageKey);
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
    if (next) {
      localStorage.setItem(storageKey, JSON.stringify(next));
      tokenStore.set(next.tokens);
    } else {
      localStorage.removeItem(storageKey);
      tokenStore.clear();
    }
  };
  const value = useMemo<Auth>(
    () => ({
      user: session?.user ?? null,
      permissions: session?.user.permissions ?? [],
      tenant: session?.user.tenant ?? null,
      workspace: session?.user.workspace ?? null,
      ready,
      login: async (email, password) => persist(await authApi.login({ email, password })),
      signup: async (email, password) => {
        await authApi.signup({ email, password });
        persist(await authApi.login({ email, password }));
      },
      logout: async () => {
        try {
          if (session) await authApi.logout(session.tokens.refreshToken);
        } finally {
          persist(null);
        }
      },
      refresh: async () => {
        if (!session) return;
        persist(await authApi.refreshSession(session.tokens.refreshToken));
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
