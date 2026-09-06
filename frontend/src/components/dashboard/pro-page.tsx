"use client";

/**
 * THE Pro page template. Every page in the six groups uses it; none keeps a
 * bespoke header.
 *
 *   title      = the sidebar label, taken from the SAME nav module, so the two
 *                cannot disagree
 *   blurb      = one plain line, "yeh page kya karta hai"
 *   action     = the SINGLE primary action, top-right (stacked on mobile)
 *   children   = the content, below
 *
 * A page passes nothing but its children in the normal case: the header is
 * derived from the route. Pass `title`/`blurb`/`action` only to override, and
 * `actionSlot` when the primary action is a dialog rather than a link.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Button } from "@/shared/ui/button";
import { navItemForPath } from "@/lib/nav/pro-nav";

export interface ProPageProps {
  title?: string;
  blurb?: string;
  action?: { label: string; href: string } | null;
  /** For a primary action that is not a link (opens a dialog, say). */
  actionSlot?: ReactNode;
  children: ReactNode;
}

export function ProPage({ title, blurb, action, actionSlot, children }: ProPageProps) {
  const pathname = usePathname();
  const item = navItemForPath(pathname ?? "/");

  const heading = title ?? item?.label ?? "";
  const line = blurb ?? item?.blurb ?? "";
  const primary = action === null ? undefined : (action ?? item?.action);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{heading}</h1>
          {line && <p className="mt-1 text-sm text-muted-foreground">{line}</p>}
        </div>
        {(actionSlot || primary) && (
          <div className="shrink-0 sm:ml-4">
            {actionSlot ?? (
              primary && (
                <Button nativeButton={false} render={<Link href={primary.href} />}>{primary.label}</Button>
              )
            )}
          </div>
        )}
      </header>
      {children}
    </div>
  );
}

/**
 * Empty state. Never just "No data" — it says what to do next, and gives the
 * one action that does it.
 */
export function ProEmpty({
  headline,
  next,
  action,
}: {
  headline: string;
  next: string;
  action?: { label: string; href: string };
}) {
  return (
    <div data-testid="start-here" className="rounded-lg border border-dashed p-8 text-center">
      <p className="font-medium">{headline}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{next}</p>
      {action && (
        <Button className="mt-4" nativeButton={false} render={<Link href={action.href} />}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
