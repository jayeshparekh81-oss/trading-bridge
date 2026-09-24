"use client";

/**
 * AccountTruthCard — per account: the open position, whether a resting stop
 * EXISTS AT THE BROKER right now (from the broker's forever-orders read), and
 * when that was last verified. Plus the one-tap "maine khud exit kar liya".
 *
 * HONESTY MECHANICS (each asserted by tests/marketplace/account-truth-card.test.tsx):
 *   - the verdict word comes from the backend; NOT MEASURED is rendered as its
 *     own state, never as a spinner and never as green;
 *   - UNPROTECTED is the ONLY red, and it says what to DO (Dhan app);
 *   - "last verified" shows the measured age or NOT MEASURED, never "just now";
 *   - the one-tap changes ONE thing (AUTO → MANUAL) and says so in the toast;
 *     it never claims the position is closed;
 *   - three states: loading / empty (FLAT) / error — none falls back to data.
 *
 * Phone-first: one column, one next step, 44px tap target on the one-tap.
 */

import { useState } from "react";
import { ShieldCheck, ShieldAlert, HelpCircle, Hand } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/shared/api/use-api";
import { api, ApiError } from "@/shared/api/client";
import { cn } from "@/shared/lib/utils";
import {
  oneTapAvailable,
  truthHeadline,
  truthTone,
  verifiedAgo,
  type ManualExitResponse,
  type TruthCard,
} from "@/lib/account-truth";

interface Props {
  subscriptionId: string;
  /** the symbol the stored row says is open (for the declaration, never for the verdict) */
  symbol: string;
  storedQuantity: number;
  className?: string;
  onDeclared?: (r: ManualExitResponse) => void;
}

const TONE_CLASS: Record<ReturnType<typeof truthTone>, string> = {
  ok: "border-profit/30 bg-profit/10 text-profit",
  danger: "border-loss/40 bg-loss/10 text-loss",
  muted: "border-border bg-muted/30 text-muted-foreground",
  unknown: "border-amber-300/30 bg-amber-400/10 text-amber-300",
};

export function AccountTruthCard({ subscriptionId, symbol, storedQuantity, className, onDeclared }: Props) {
  const { data, isLoading, error, refetch } = useApi<TruthCard>("/customer-lane/dashboard/truth");
  const [declaring, setDeclaring] = useState(false);

  async function declare() {
    setDeclaring(true);
    try {
      const r = await api.post<ManualExitResponse>("/customer-lane/dashboard/manual-exit", {
        subscription_id: subscriptionId,
        symbol,
        stored_quantity: storedQuantity,
        note: "one-tap",
      });
      toast.success(r.message_hi, { duration: 8000 });
      onDeclared?.(r);
      refetch();
    } catch (e) {
      toast.error(e instanceof ApiError ? String(e.detail) : "Abhi record nahi hua — thodi der me phir dabao.");
    } finally {
      setDeclaring(false);
    }
  }

  if (isLoading && !data) {
    return (
      <div data-testid="truth-loading" className={cn("rounded-lg border border-border p-3 text-11 text-muted-foreground", className)}>
        Broker se stop ki haalat dekh rahe hain…
      </div>
    );
  }
  if (error && !data) {
    return (
      <div data-testid="truth-error" className={cn("rounded-lg border border-amber-300/30 bg-amber-400/10 p-3 text-11", className)}>
        Yeh card abhi load nahi hua. Apne Dhan app me stop khud dekh lo, phir yahan dobara try karo.
        <button type="button" onClick={refetch} className="ml-2 underline">Dobara</button>
      </div>
    );
  }
  if (!data) return null;

  const tone = truthTone(data.verdict);
  const Icon = tone === "ok" ? ShieldCheck : tone === "danger" ? ShieldAlert : HelpCircle;
  const pos = data.position;

  return (
    <div data-testid="truth-card" data-verdict={data.verdict} className={cn("rounded-lg border p-3 space-y-2", TONE_CLASS[tone], className)}>
      <div className="flex items-start gap-2">
        <Icon aria-hidden="true" className="h-4 w-4 mt-0.5 shrink-0" />
        <div className="min-w-0 space-y-1">
          <div data-testid="truth-headline" className="text-xs font-semibold">{truthHeadline(data.verdict)}</div>
          {pos ? (
            <div data-testid="truth-position" className="text-11 text-foreground/90">
              Position: {pos.side ?? "?"} {pos.quantity ?? "?"} {pos.symbol ?? ""}
            </div>
          ) : (
            <div data-testid="truth-position" className="text-11">Koi position nahi.</div>
          )}
          <div data-testid="truth-verified" className="text-10 text-foreground/70">
            Dhan se last check: {verifiedAgo(data.age_s)}
            {data.stop?.order_id ? ` · stop order ${data.stop.order_id}` : ""}
          </div>
          <div data-testid="truth-next-step" className="text-11">{data.next_step_hi}</div>
        </div>
      </div>
      {oneTapAvailable(data) ? (
        <button
          type="button"
          data-testid="one-tap-manual-exit"
          onClick={declare}
          disabled={declaring}
          className="w-full min-h-11 rounded-md border border-border bg-background/60 text-xs font-medium flex items-center justify-center gap-2 disabled:opacity-60"
        >
          <Hand aria-hidden="true" className="h-4 w-4" />
          Maine khud exit kar liya
        </button>
      ) : null}
    </div>
  );
}
