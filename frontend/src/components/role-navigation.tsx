"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { navigationForRole } from "@/lib/navigation";
import type { Role } from "@/types";
export function RoleNavigation({ role, onNavigate }: { role: Role; onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Product navigation">
      {navigationForRole(role).map((item) => (
        <Link
          onClick={onNavigate}
          className={path === item.href || path.startsWith(item.href + "/") ? "active" : ""}
          href={item.href}
          key={item.href}
        >
          <item.icon />
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
