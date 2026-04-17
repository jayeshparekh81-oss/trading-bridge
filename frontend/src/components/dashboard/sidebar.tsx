"use client";

import { cn } from "@/lib/utils";
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
  Zap,
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

const navItems: NavItem[] = [
  { label: "Overview", href: "/", icon: BarChart3 },
  { label: "Brokers", href: "/brokers", icon: Landmark },
  { label: "Positions", href: "/positions", icon: LineChart },
  { label: "Trades", href: "/trades", icon: ListOrdered },
  { label: "Strategies", href: "/strategies", icon: Bot },
  { label: "Kill Switch", href: "/kill-switch", icon: ShieldAlert },
  { label: "Analytics", href: "/analytics", icon: TrendingUp },
  { label: "Webhooks", href: "/webhooks", icon: Webhook },
  { label: "Alerts", href: "/alerts", icon: Bell },
  { label: "Settings", href: "/settings", icon: Settings },
];

const adminItem: NavItem = {
  label: "Admin",
  href: "/admin",
  icon: Crown,
  adminOnly: true,
};

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
        <Zap className="h-6 w-6 text-accent-blue shrink-0" />
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="font-bold text-lg whitespace-nowrap overflow-hidden"
            >
              TradeForge
            </motion.span>
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

        {/* Separator + Admin */}
        <div className="my-4 border-t border-sidebar-border" />
        <Link
          href={adminItem.href}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
            "hover:bg-sidebar-accent",
            pathname === adminItem.href
              ? "bg-sidebar-accent text-accent-gold"
              : "text-sidebar-foreground/70"
          )}
        >
          <Crown className={cn("h-5 w-5 shrink-0", pathname === adminItem.href && "text-accent-gold")} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="whitespace-nowrap overflow-hidden"
              >
                Admin
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
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
