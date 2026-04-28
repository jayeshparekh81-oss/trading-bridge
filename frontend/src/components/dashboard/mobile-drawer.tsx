"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  Menu,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: typeof BarChart3;
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

const adminItems: NavItem[] = [
  { label: "System Health", href: "/admin", icon: Crown },
  { label: "Users", href: "/admin/users", icon: Crown },
  { label: "Audit Logs", href: "/admin/audit", icon: Crown },
  { label: "KS Events", href: "/admin/kill-switch-events", icon: ShieldAlert },
  { label: "Announce", href: "/admin/announcements", icon: Bell },
];

export function MobileDrawer() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  const renderItem = (item: NavItem, isAdmin: boolean) => {
    const isActive = pathname === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={() => setOpen(false)}
        className={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          "hover:bg-sidebar-accent",
          isActive
            ? isAdmin
              ? "bg-accent-purple/10 text-accent-purple border-l-2 border-accent-purple"
              : "bg-sidebar-accent text-sidebar-primary border-l-2 border-sidebar-primary"
            : "text-sidebar-foreground/70"
        )}
      >
        <item.icon
          className={cn(
            "h-5 w-5 shrink-0",
            isActive &&
              (isAdmin ? "text-accent-purple" : "text-sidebar-primary")
          )}
        />
        <span>{item.label}</span>
      </Link>
    );
  };

  return (
    <Sheet open={open} onOpenChange={(value) => setOpen(value)}>
      <SheetTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation"
          />
        }
      >
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent
        side="left"
        className="w-[280px] bg-sidebar p-0 border-r border-sidebar-border"
      >
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex items-center gap-2 px-4 h-16 border-b border-sidebar-border">
          <Logo variant="icon" width={36} height={36} />
          <Logo variant="wordmark" height={36} />
        </div>
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
          {navItems.map((item) => renderItem(item, false))}
          <div className="my-4 border-t border-sidebar-border" />
          {adminItems.map((item) => renderItem(item, true))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
