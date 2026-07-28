import {
  Bell,
  Bot,
  CalendarClock,
  Coins,
  CreditCard,
  FileText,
  Gauge,
  Globe2,
  LayoutDashboard,
  Library,
  Settings,
  Shield,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/types";
export type NavItem = { label: string; href: string; icon: LucideIcon; roles?: Role[] };
export const navigation: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, roles: ["Owner", "SuperAdmin"] },
  { label: "AI Studio", href: "/ai-studio", icon: Bot },
  { label: "Content", href: "/content", icon: Library },
  { label: "Scheduler", href: "/scheduler", icon: CalendarClock },
  { label: "Publishing", href: "/publishing", icon: Globe2 },
  { label: "Scraper", href: "/scraper", icon: FileText },
  { label: "Usage", href: "/usage", icon: Gauge },
  { label: "Credits", href: "/credits", icon: Coins, roles: ["Owner", "SuperAdmin"] },
  { label: "Billing", href: "/billing", icon: CreditCard, roles: ["Owner", "SuperAdmin"] },
  { label: "Team", href: "/team", icon: Users, roles: ["Owner", "Admin", "Member", "SuperAdmin"] },
  { label: "Notifications", href: "/notifications", icon: Bell },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "Operations", href: "/admin", icon: Shield, roles: ["SuperAdmin"] },
];
export const navigationForRole = (role: Role) =>
  navigation.filter((item) => !item.roles || item.roles.includes(role));
