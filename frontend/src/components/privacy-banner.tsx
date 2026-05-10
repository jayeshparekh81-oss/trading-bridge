"use client";

/**
 * First-visit privacy banner.
 *
 * Renders only on the client (gated by ``useSyncExternalStore``
 * snapshot of the dismissal flag) so the SSR HTML never includes
 * the banner — no flash on hydrate.
 *
 * Three buttons:
 *   * "Theek hai" — dismiss + leave analytics ON.
 *   * "Opt out" — dismiss + flip the opt-out localStorage flag.
 *   * Close (X) — equivalent to "Theek hai".
 *
 * Once dismissed (either way) the banner stays hidden across
 * sessions because the dismissal flag persists.
 */

import { useCallback, useSyncExternalStore } from "react";
import { motion } from "framer-motion";
import { Shield, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { setOptedOut } from "@/lib/analytics";
import { cn } from "@/lib/utils";

const DISMISSAL_KEY = "tradetri_analytics_banner_dismissed";

function readDismissed(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(DISMISSAL_KEY) === "true";
  } catch {
    return true;
  }
}

function writeDismissed(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(DISMISSAL_KEY, "true");
  } catch {
    // localStorage may throw in private mode — accept the
    // re-display on next visit.
  }
}

const _subscribers = new Set<() => void>();

function subscribe(cb: () => void): () => void {
  _subscribers.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === DISMISSAL_KEY) cb();
  };
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    _subscribers.delete(cb);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

function notify(): void {
  for (const cb of _subscribers) cb();
}

function serverSnapshot(): boolean {
  // Server snapshot reports "dismissed" so SSR HTML doesn't
  // include the banner; the client first-paint reconciles to
  // the persisted value.
  return true;
}

export function PrivacyBanner() {
  const dismissed = useSyncExternalStore(
    subscribe,
    readDismissed,
    serverSnapshot,
  );

  const handleAccept = useCallback(() => {
    writeDismissed();
    notify();
  }, []);

  const handleOptOut = useCallback(() => {
    setOptedOut(true);
    writeDismissed();
    notify();
  }, []);

  if (dismissed) return null;

  return (
    <motion.div
      initial={{ y: 80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 80, opacity: 0 }}
      transition={{ type: "spring", stiffness: 280, damping: 24 }}
      className={cn(
        "fixed bottom-4 left-1/2 -translate-x-1/2 z-50",
        "w-full max-w-xl px-4",
      )}
      role="region"
      aria-label="Privacy notice"
    >
      <div
        className={cn(
          "rounded-xl border border-white/[0.08] bg-popover/95 backdrop-blur-xl",
          "shadow-[0_8px_40px_rgba(0,0,0,0.4)]",
          "p-4 flex items-start gap-3",
        )}
      >
        <Shield className="h-4 w-4 text-accent-blue shrink-0 mt-0.5" />
        <div className="flex-1 space-y-2 min-w-0">
          <p className="text-sm font-semibold">Privacy Notice</p>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Hum analytics use karte hain TRADETRI ko behtar banane
            ke liye — koi PII (email / phone / name) nahi bhejte,
            user IDs hashed jaate hain. Opt out kabhi bhi kar sakte
            ho.
          </p>
          <div className="flex items-center gap-2 flex-wrap pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAccept}
              type="button"
            >
              Theek hai
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleOptOut}
              type="button"
            >
              Opt out
            </Button>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={handleAccept}
          type="button"
          aria-label="Dismiss privacy banner"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </motion.div>
  );
}
