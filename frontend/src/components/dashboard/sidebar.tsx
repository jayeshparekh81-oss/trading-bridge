"use client";

import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  Landmark,
  LineChart,
  ListOrdered,
  Bot,
  ShieldAlert,
  TrendingUp,
  Webhook,
  Bell,
  Settings,
  Crown,
  ChevronLeft,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: typeof BarChart3;
  comingSoon?: boolean;
}

// Sidebar nav — full 14-entry list. Pages with ``comingSoon: true``
// render the shared ComingSoon placeholder (no mock data leakage).
//
// Wiring status (Sun 2026-05-03 sprint):
//   ✅ wired:        Overview, Brokers, Positions, Trades, Kill Switch,
//                     Strategies (read-only)
//   🚧 placeholder:  Analytics, Webhooks, Alerts, Settings,
//                     System Health, Users, Audit Logs, KS Events, Announce
//
// Re-wire each by replacing src/app/(dashboard)/<route>/page.tsx with
// real backend wiring AND removing the ``comingSoon`` flag below. See
// docs/FRONTEND_NEXT_SPRINT.md for endpoints + estimates.
const navItems: NavItem[] = [
  { label: "Overview", href: "/", icon: BarChart3 },
  { label: "Brokers", href: "/brokers", icon: Landmark },
  { label: "Positions", href: "/positions", icon: LineChart },
  { label: "Trades", href: "/trades", icon: ListOrdered },
  { label: "Strategies", href: "/strategies", icon: Bot },
  { label: "Kill Switch", href: "/kill-switch", icon: ShieldAlert },
  { label: "Analytics", href: "/analytics", icon: TrendingUp, comingSoon: true },
  { label: "Webhooks", href: "/webhooks", icon: Webhook, comingSoon: true },
  { label: "Alerts", href: "/alerts", icon: Bell, comingSoon: true },
  { label: "Settings", href: "/settings", icon: Settings, comingSoon: true },
];

const adminItems: NavItem[] = [
  { label: "System Health", href: "/admin", icon: Crown, comingSoon: true },
  { label: "Users", href: "/admin/users", icon: Crown, comingSoon: true },
  { label: "Audit Logs", href: "/admin/audit", icon: Crown, comingSoon: true },
  { label: "KS Events", href: "/admin/kill-switch-events", icon: ShieldAlert, comingSoon: true },
  { label: "Announce", href: "/admin/announcements", icon: Bell, comingSoon: true },
];

function NavLink({
  item,
  pathname,
  collapsed,
  variant = "primary",
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
  variant?: "primary" | "admin";
}) {
  const isActive = pathname === item.href;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
        "hover:bg-sidebar-accent",
        isActive && variant === "primary"
          ? "bg-sidebar-accent text-sidebar-primary border-l-2 border-sidebar-primary"
          : isActive && variant === "admin"
          ? "bg-accent-purple/10 text-accent-purple border-l-2 border-accent-purple"
          : "text-sidebar-foreground/70",
      )}
    >
      <item.icon
        className={cn(
          "h-5 w-5 shrink-0",
          isActive && variant === "primary" && "text-sidebar-primary",
          isActive && variant === "admin" && "text-accent-purple",
        )}
      />
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            className={cn(
              "whitespace-nowrap overflow-hidden flex-1 flex items-center gap-2",
              variant === "admin" && "text-xs",
            )}
          >
            <span>{item.label}</span>
            {item.comingSoon && (
              <span
                className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase tracking-wide shrink-0"
                title="Coming soon — placeholder"
              >
                Soon
              </span>
            )}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="hidden md:flex flex-col h-full border-r border-sidebar-border bg-sidebar"
    >
      <div className="flex items-center gap-2 px-4 h-16 border-b border-sidebar-border">
        <div className="shrink-0">
          <Logo variant="icon" width={40} height={40} />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="whitespace-nowrap overflow-hidden"
            >
              <Logo variant="wordmark" height={40} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
        ))}

        <div className="my-4 border-t border-sidebar-border" />
        {adminItems.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            pathname={pathname}
            collapsed={collapsed}
            variant="admin"
          />
        ))}
      </nav>

      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-12 border-t border-sidebar-border hover:bg-sidebar-accent transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <motion.div animate={{ rotate: collapsed ? 180 : 0 }}>
          <ChevronLeft className="h-4 w-4 text-muted-foreground" />
        </motion.div>
      </button>
    </motion.aside>
  );
}
