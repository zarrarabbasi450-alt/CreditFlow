"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { navigation } from "@/lib/navigation";
import { RoleNavigation } from "./role-navigation";
import { ThemeToggle } from "./theme-toggle";
import { CommandPalette } from "./command-palette";
import { NotificationBell } from "./notification-bell";
import { WorkspaceSwitcher } from "./workspace-switcher";
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, ready, logout } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [mobile, setMobile] = useState(false);
  const section = path.split("/").filter(Boolean)[0];
  const navItem = navigation.find((entry) => entry.href === `/${section}`);
  const forbidden = !!user && !!navItem?.roles && !navItem.roles.includes(user.role);
  useEffect(() => {
    if (ready && !user) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [ready, user, router, path]);
  useEffect(() => {
    // Nav-link hiding alone isn't a guard — a Member can still type /admin into the
    // address bar. This redirects away from any section the signed-in role can't see.
    if (forbidden) router.replace("/content");
  }, [forbidden, router]);
  if (!ready || !user || forbidden)
    return (
      <div className="loading-screen">
        <Sparkles className="animate-pulse" />
        Preparing your workspace…
      </div>
    );
  const crumbs = path.split("/").filter(Boolean);
  return (
    <div className="app-frame">
      <aside className={mobile ? "mobile-open" : ""}>
        <div className="brand">
          <span>
            <Sparkles />
          </span>
          CreditFlow
          <button aria-label="Close navigation" onClick={() => setMobile(false)}>
            <X />
          </button>
        </div>
        <WorkspaceSwitcher />
        <RoleNavigation role={user.role} onNavigate={() => setMobile(false)} />
        <div className="sidebar-foot">
          <div className="avatar">
            {user.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </div>
          <div>
            <strong>{user.name}</strong>
            <small>{user.email}</small>
          </div>
          <button
            aria-label="Sign out"
            onClick={() => {
              void logout();
              router.push("/login");
            }}
          >
            <LogOut />
          </button>
        </div>
      </aside>
      {mobile && (
        <button
          aria-label="Close navigation overlay"
          className="nav-overlay"
          onClick={() => setMobile(false)}
        />
      )}
      <main>
        <header>
          <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobile(true)}>
            <Menu />
          </button>
          <div className="breadcrumbs">
            <Link href="/content">Workspace</Link>
            {crumbs.map((crumb) => (
              <span key={crumb}>
                / <strong>{crumb.replaceAll("-", " ")}</strong>
              </span>
            ))}
          </div>
          <CommandPalette />
          <ThemeToggle />
          <NotificationBell />
          <span className="role-badge" title="Your verified access role">
            {user.role}
          </span>
        </header>
        <div className="page-wrap">{children}</div>
      </main>
    </div>
  );
}
