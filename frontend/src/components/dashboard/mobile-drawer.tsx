"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Menu } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/shared/ui/sheet";
import { Logo } from "@/components/logo";
import { cn } from "@/shared/lib/utils";
import { useAuth } from "@/lib/auth";
import { PRO_NAV, ADMIN_NAV, type ProNavItem } from "@/lib/nav/pro-nav";

// SAME list as the desktop sidebar, imported from the same module. The previous
// comment here said "keep in sync with sidebar.tsx" and it had not been: the
// drawer was missing three entries and called the kill switch by a different
// name. A shared module makes identical structural instead of a chore.

export function MobileDrawer() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const isCreator = isAdmin || ["creator", "admin", "super_admin"].includes(String(user?.role ?? ""));
  const canSee = (item: ProNavItem) =>
    (!item.adminOnly || isAdmin) && (!item.creatorOnly || isCreator);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  const renderItem = (item: ProNavItem, isAdmin: boolean) => {
    const isActive = pathname === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={() => setOpen(false)}
        {...(item.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        className={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          "hover:bg-sidebar-accent",
          isActive
            ? isAdmin
              ? "bg-accent-purple/10 text-accent-purple border-l-2 border-accent-purple"
              : "bg-sidebar-accent text-sidebar-primary border-l-2 border-sidebar-primary"
            : "text-sidebar-foreground/70",
        )}
      >
        <item.icon
          className={cn(
            "h-5 w-5 shrink-0",
            isActive && (isAdmin ? "text-accent-purple" : "text-sidebar-primary"),
          )}
        />
        <span className="flex-1">{item.label}</span>
      </Link>
    );
  };

  return (
    <Sheet open={open} onOpenChange={(value) => setOpen(value)}>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation" />
        }
      >
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-[280px] bg-sidebar p-0 border-r border-sidebar-border">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex items-center gap-2 px-4 h-16 border-b border-sidebar-border">
          <Logo variant="icon" width={36} height={36} />
          <Logo variant="wordmark" height={36} />
        </div>
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
          {PRO_NAV.map((group) => {
            const visible = group.items.filter((item) => canSee(item));
            if (visible.length === 0) return null;
            return (
              <div key={group.title} className="pb-2">
                <p className="px-3 pt-3 pb-1 text-xs text-muted-foreground">{group.title}</p>
                {visible.map((item) => (
                  <div key={item.href}>
                    {renderItem(item, false)}
                    {item.children?.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        onClick={() => setOpen(false)}
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
              {ADMIN_NAV.map((item) => renderItem(item, true))}
            </>
          )}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
