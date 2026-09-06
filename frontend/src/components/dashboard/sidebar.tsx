"use client";

import { cn } from "@/shared/lib/utils";
import { Logo } from "@/components/logo";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { SIDEBAR_EXPAND_EVENT } from "@/components/simple/pro-welcome-nudge";
import { useAuth } from "@/lib/auth";
import { PRO_NAV, ADMIN_NAV, type ProNavItem } from "@/lib/nav/pro-nav";

// The list lives in @/lib/nav/pro-nav and is shared with the mobile drawer, so the
// two can never drift again. They had: the drawer was missing three entries and
// called the kill switch by a different name.

// Sidebar nav hrefs mapped to onboarding-tour anchor ids. Adding the
// `data-tour-id` here keeps targeting stable for tourSteps.ts even if
// the label or icon changes.
const TOUR_ID_BY_HREF: Record<string, string> = {
  "/brokers": "brokers-nav",
  "/chart": "chart-nav",
  "/strategies": "strategies-nav",
  "/strategies/templates": "templates-nav",
};

function NavLink({
  item,
  pathname,
  collapsed,
  variant = "primary",
}: {
  item: ProNavItem;
  pathname: string;
  collapsed: boolean;
  variant?: "primary" | "admin";
}) {
  const isActive = pathname === item.href;
  const tourId = TOUR_ID_BY_HREF[item.href];
  return (
    <Link
      href={item.href}
      data-tour-id={tourId}
      {...(item.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
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
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}

export function Sidebar() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const isCreator = isAdmin || ["creator", "admin", "super_admin"].includes(String(user?.role ?? ""));
  const canSee = (item: ProNavItem) =>
    (!item.adminOnly || isAdmin) && (!item.creatorOnly || isCreator);
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  // First time Pro opens, the ladder asks for the full menu to be shown once.
  useEffect(() => {
    const onExpand = () => setCollapsed(false);
    window.addEventListener(SIDEBAR_EXPAND_EVENT, onExpand);
    return () => window.removeEventListener(SIDEBAR_EXPAND_EVENT, onExpand);
  }, []);

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
        {PRO_NAV.map((group) => {
          const visible = group.items.filter((item) => canSee(item));
          if (visible.length === 0) return null;
          return (
            <div key={group.title} className="pb-2">
              <AnimatePresence>
                {!collapsed && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="px-3 pt-3 pb-1 text-xs text-muted-foreground"
                  >
                    {group.title}
                  </motion.p>
                )}
              </AnimatePresence>
              {visible.map((item) => (
                <div key={item.href}>
                  <NavLink item={item} pathname={pathname} collapsed={collapsed} />
                  {!collapsed &&
                    item.children?.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={cn(
                          "block rounded-lg py-1.5 pl-11 pr-3 text-sm transition-colors",
                          pathname === child.href
                            ? "text-sidebar-primary"
                            : "text-sidebar-foreground/60 hover:text-sidebar-foreground",
                        )}
                      >
                        {child.label}
                      </Link>
                    ))}
                </div>
              ))}
            </div>
          );
        })}

        {isAdmin && (
          <>
            <div className="my-4 border-t border-sidebar-border" />
            {ADMIN_NAV.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                pathname={pathname}
                collapsed={collapsed}
                variant="admin"
              />
            ))}
          </>
        )}
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
