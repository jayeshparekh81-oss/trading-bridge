"use client";

import { cn } from "@/lib/utils";
import { } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ALL_PRO_ITEMS } from "@/lib/nav/pro-nav";

// Mobile bottom-tab nav — keep in sync with sidebar.tsx and
// mobile-drawer.tsx. Only 5 slots, so this is the journey's spine. Strategies + Settings hidden until wired
// (see docs/FRONTEND_NEXT_SPRINT.md). Replaced with Brokers + Kill
// Switch which are real-data Tier-1 pages.
// The bottom bar is a SHORTCUT surface, not the full menu — five destinations
// only. But its labels must be the SAME words as the sidebar and the drawer, so
// they are looked up from the shared nav module by href rather than retyped.
// They had drifted: this bar said "Sab band" where the sidebar said "Kill Switch".
const SHORTCUT_HREFS = ["/", "/positions", "/marketplace/me", "/brokers", "/kill-switch"] as const;

const mobileItems = SHORTCUT_HREFS.map((href) => {
  const item = ALL_PRO_ITEMS.find((i) => i.href === href);
  if (!item) throw new Error(`mobile-nav shortcut ${href} is not in PRO_NAV`);
  return { label: item.label, href: item.href, icon: item.icon };
});

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 md:hidden bg-background/90 backdrop-blur-lg border-t border-border z-50 safe-area-bottom">
      <div className="flex items-center justify-around h-16">
        {mobileItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-0.5 py-2 px-3 rounded-lg transition-colors",
                isActive
                  ? "text-accent-blue"
                  : "text-muted-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
