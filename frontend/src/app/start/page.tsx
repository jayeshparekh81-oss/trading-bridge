"use client";

/**
 * /start — ONE guided path from signup to a running strategy (founder, 26 Sep 2026).
 *
 * Behind NEXT_PUBLIC_CUSTOMER_GUIDED_PATH (OFF): unset, this page renders the honest
 * "not switched on" line and nothing else, so a publish changes nothing a customer sees
 * until the flag is flipped. Declared in tests/architecture/route-map.test.ts.
 */

import Link from "next/link";

import { GuidedPath } from "@/components/guided/guided-path";
import { guidedPathEnabled } from "@/lib/guided-path";

export default function StartPage() {
  if (!guidedPathEnabled()) {
    return (
      <p data-testid="guided-off" className="text-sm text-muted-foreground">
        Yeh guide abhi chalu nahi hai. <Link href="/register" className="underline">Account banao</Link> ya{" "}
        <Link href="/login" className="underline">login karo</Link>.
      </p>
    );
  }
  return <GuidedPath />;
}
