"use client";

/**
 * The Subscribe path off a public showcase card.
 *
 * DATA-DRIVEN, not hardcoded to s1. It renders only when the API reports a
 * published `listing_id` for that strategy, so a card with no listing (s3 is
 * paper; s2 has no listing) shows no control at all — never a dead or disabled
 * one. The day a listing is published, the button appears on its own.
 *
 * ⚠️ THE MASK. /showcase is PUBLIC and s1/s2/s3 exist to hide which strategy
 * is which. This component puts a `listing_id` in the public HTML, which makes
 * the pairing "s1 ↔ that listing" readable by anyone. That is safe ONLY while
 * the listing's own copy is masked too — title "Strategy S1", generic
 * description, no instrument tags. Registration is self-serve, so an
 * instrument-named listing would cost exactly one free signup to unmask. This
 * component cannot enforce that; the listing copy is a data decision. It is
 * stated here, in the endpoint, and in the deploy checklist.
 *
 * It NAVIGATES rather than subscribing. The listing page already owns the
 * proven subscribe flow (and the post-subscribe redirect into Deploy, where
 * even-quantity lives), so there is no second subscribe implementation to keep
 * in step with the first.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { withNext } from "@/lib/safe-next";
import { cn } from "@/lib/utils";

export function ShowcaseSubscribeCta({
  listingId,
  className,
}: {
  listingId?: string | null;
  className?: string;
}) {
  const { user, isLoading } = useAuth();

  // No published listing => no control. Nothing to subscribe to yet.
  if (!listingId) return null;

  const target = `/marketplace/${listingId}`;

  // While the session is still resolving we do NOT guess. Rendering the
  // logged-out href here would march an already-logged-in customer to the
  // register form; rendering the logged-in one would drop a logged-out visitor
  // onto a page that 401s. A brief inert placeholder is the honest third
  // option — it keeps the layout from jumping, and resolves in a few hundred ms.
  if (isLoading) {
    return (
      <div
        data-testid="showcase-subscribe-loading"
        aria-hidden
        className={cn(
          "inline-flex items-center rounded-lg bg-white/[0.04] px-4 py-2",
          "text-sm text-transparent select-none",
          className,
        )}
      >
        Subscribe
      </div>
    );
  }

  // Logged out => register first, then come STRAIGHT back to this strategy.
  // Without the ?next= the customer lands on a generic dashboard and has to
  // find their way back to the thing they were looking at.
  const href = user ? target : withNext("/register", target);

  return (
    <Link
      href={href}
      data-testid="showcase-subscribe"
      data-authed={user ? "yes" : "no"}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-4 py-2",
        "bg-primary text-primary-foreground text-sm font-semibold",
        "hover:opacity-90 transition-opacity",
        className,
      )}
    >
      Subscribe
      <ArrowRight className="h-3.5 w-3.5" />
    </Link>
  );
}
