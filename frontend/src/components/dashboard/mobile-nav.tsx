"use client";

import { cn } from "@/lib/utils";
import { BarChart3, LineChart, ListOrdered, Bot, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const mobileItems = [
  { label: "Home", href: "/", icon: BarChart3 },
  { label: "Positions", href: "/positions", icon: LineChart },
  { label: "Trades", href: "/trades", icon: ListOrdered },
  { label: "Strategies", href: "/strategies", icon: Bot },
  { label: "Settings", href: "/settings", icon: Settings },
];

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
