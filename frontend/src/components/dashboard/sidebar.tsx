"use client";

import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  Landmark,
  LineChart,
  ListOrdered,
  ShieldAlert,
  ChevronLeft,
  } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: typeof BarChart3;
  adminOnly?: boolean;
}

// Sidebar nav — only shows pages wired to real backend data.
//
// HIDDEN until properly wired (see docs/FRONTEND_NEXT_SPRINT.md):
//   - /strategies   (mock data; backend CRUD ready, needs UX)
//   - /webhooks     (mock data; needs new "recent hits" endpoint)
//   - /alerts       (mock data; backend endpoint doesn't exist yet)
//   - /settings     (mock data; out of confirmed Tier-1 scope)
//   - /analytics    (mock data; needs aggregation endpoint)
//   - /admin/*      (mock data; admin features deferred)
//
// Re-enable by adding the entry back here AND in mobile-drawer.tsx /
// mobile-nav.tsx (same list duplicated). Routes themselves still exist
// so direct URL access still works for testing.
const navItems: NavItem[] = [
  { label: "Overview", href: "/", icon: BarChart3 },
  { label: "Brokers", href: "/brokers", icon: Landmark },
  { label: "Positions", href: "/positions", icon: LineChart },
  { label: "Trades", href: "/trades", icon: ListOrdered },
  { label: "Kill Switch", href: "/kill-switch", icon: ShieldAlert },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="hidden md:flex flex-col h-full border-r border-sidebar-border bg-sidebar"
    >
      {/* Logo */}
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

      {/* Nav items */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                "hover:bg-sidebar-accent",
                isActive
                  ? "bg-sidebar-accent text-sidebar-primary border-l-2 border-sidebar-primary"
                  : "text-sidebar-foreground/70"
              )}
            >
              <item.icon className={cn("h-5 w-5 shrink-0", isActive && "text-sidebar-primary")} />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: "auto" }}
                    exit={{ opacity: 0, width: 0 }}
                    className="whitespace-nowrap overflow-hidden"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          );
        })}

        {/* Admin section hidden — see comment above navItems */}
      </nav>

      {/* Collapse toggle */}
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
