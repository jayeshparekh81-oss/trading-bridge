"use client";

import { Bell, Moon, Sun, Monitor, Search, LogOut, User, Settings, Palette, Type, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useCustomTheme } from "@/lib/theme-context";
import { themes } from "@/lib/themes";
import { fontPairs } from "@/lib/fonts";
import { cn } from "@/lib/utils";
import { MobileDrawer } from "@/components/dashboard/mobile-drawer";

interface TopBarProps {
  userName: string;
  notificationCount?: number;
  onLogout?: () => void;
}

export function TopBar({ userName, notificationCount = 0, onLogout }: TopBarProps) {
  const { theme, setTheme, font, setFont, mode, setMode } = useCustomTheme();

  const initials = userName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const cycleMode = () => {
    const modes: Array<'auto' | 'dark' | 'light'> = ['auto', 'dark', 'light'];
    const idx = modes.indexOf(mode);
    setMode(modes[(idx + 1) % modes.length]);
  };

  const ModeIcon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor;

  return (
    <header className="flex items-center justify-between h-16 px-4 md:px-6 border-b border-border bg-background/80 backdrop-blur-lg sticky top-0 z-40">
      {/* Left: Mobile drawer trigger + Search */}
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <MobileDrawer />
        <div className="relative w-full hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search... (Ctrl+K)"
            className="w-full h-9 pl-9 pr-4 rounded-lg bg-muted/50 border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="h-5 w-5" />
          {notificationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-loss text-[10px] font-bold text-white flex items-center justify-center">
              {notificationCount > 9 ? "9+" : notificationCount}
            </span>
          )}
        </Button>

        {/* Mode toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={cycleMode}
          aria-label="Toggle mode"
          title={`Mode: ${mode}`}
        >
          <ModeIcon className="h-5 w-5" />
        </Button>

        {/* Theme dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground h-9 w-9 cursor-pointer" aria-label="Theme">
              <Palette className="h-5 w-5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {themes.map((t) => (
              <DropdownMenuItem
                key={t.id}
                onClick={() => t.active && setTheme(t.id)}
                disabled={!t.active}
                className={cn(
                  "flex items-center justify-between",
                  !t.active && "opacity-50"
                )}
              >
                <span className="flex items-center gap-2">
                  <span>{t.emoji}</span>
                  <span className="text-xs">{t.name}</span>
                </span>
                {theme === t.id && <Check className="h-3 w-3 text-primary" />}
                {t.comingSoon && <span className="text-[9px] text-muted-foreground">Soon</span>}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Font dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground h-9 w-9 cursor-pointer" aria-label="Font">
              <Type className="h-5 w-5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {fontPairs.map((fp) => (
              <DropdownMenuItem
                key={fp.id}
                onClick={() => setFont(fp.id)}
                className="flex items-center justify-between"
              >
                <span className="flex items-center gap-2">
                  <span>{fp.emoji}</span>
                  <span className="text-xs">{fp.name}</span>
                </span>
                {font === fp.id && <Check className="h-3 w-3 text-primary" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-accent transition-colors outline-none">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary/20 text-primary text-xs font-bold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <span className="hidden md:inline text-sm font-medium">{userName}</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem>
              <User className="mr-2 h-4 w-4" /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Settings className="mr-2 h-4 w-4" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-loss" onClick={onLogout}>
              <LogOut className="mr-2 h-4 w-4" /> Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
