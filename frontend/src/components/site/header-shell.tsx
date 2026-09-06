"use client";

/**
 * ONE FACE (founder, 2026-09-05): the public site and the app render the SAME
 * header shell — height, background, border, blur, logo sizes, horizontal
 * padding. Only the slots differ (public nav vs the app's drawer trigger and
 * actions) and how it sticks (the public pages are built for a fixed header).
 */

import type { ReactNode } from "react";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

/** The shared tokens — a test pins both headers to this exact string. */
export const HEADER_SHELL_TOKENS = "h-16 border-b border-border bg-background/80 backdrop-blur-lg";
export const HEADER_INNER_TOKENS = "flex h-16 items-center justify-between gap-3 px-4 md:px-6";
export const HEADER_LOGO = { icon: 32, wordmark: 26 } as const;

export function HeaderLogo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2", className)} aria-label="TRADETRI" data-testid="header-logo">
      <Logo variant="icon" width={HEADER_LOGO.icon} height={HEADER_LOGO.icon} priority />
      <Logo variant="wordmark" height={HEADER_LOGO.wordmark} />
    </Link>
  );
}

export interface HeaderShellProps {
  left?: ReactNode;
  center?: ReactNode;
  right?: ReactNode;
  /** Anything rendered under the bar (the public mobile menu). */
  below?: ReactNode;
  /** "fixed": overlays the page (public pages pad for it). "sticky": in flow (the app). */
  position?: "fixed" | "sticky";
  /** Constrain the inner row to the site's max width (public); the app spans its column. */
  contained?: boolean;
  className?: string;
  testid?: string;
}

export function HeaderShell({ left, center, right, below, position = "sticky", contained = false, className, testid }: HeaderShellProps) {
  return (
    <header
      className={cn(position === "fixed" ? "fixed top-0 left-0 right-0 z-50" : "sticky top-0 z-40", HEADER_SHELL_TOKENS, below ? "h-auto" : null, className)}
      data-testid={testid ?? "header-shell"}
      data-header-shell="v1"
    >
      <div className={cn(HEADER_INNER_TOKENS, contained ? "mx-auto max-w-7xl" : null)}>
        <div className="flex items-center gap-3 min-w-0">{left}</div>
        {center ? <div className="hidden md:flex items-center gap-8">{center}</div> : null}
        <div className="flex items-center gap-2">{right}</div>
      </div>
      {below}
    </header>
  );
}
