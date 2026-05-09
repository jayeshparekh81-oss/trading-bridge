"use client";

/**
 * Go Live confirmation modal — collects order details and submits.
 *
 * Defaults to ``dry_run=true`` so the safe path requires explicit
 * opt-in for real money. The Confirm button changes colour + icon
 * + label between the two modes so the user can never miss the
 * difference between testing and trading.
 *
 * Submits to POST /api/orders/live; success and structured-block
 * results both surface through the parent's ``onResult`` callback,
 * which renders an `OrderResultCard` inline. Hard HTTP errors
 * (503, 422 strategy-misconfigured, 401 expired) raise a Sonner
 * toast and leave the modal open so the user can retry.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, FlaskConical, Loader2, Rocket, X } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Wire types ─────────────────────────────────────────────────────────

import type { SafetyChainResult } from "./safety-pre-flight-panel";

export interface LiveOrderResult {
  success: boolean;
  order_id: string | null;
  safety_chain_result: SafetyChainResult;
  broker_guard_passed: boolean;
  broker_response: Record<string, unknown> | null;
  audit_log_id: string;
  placed_at: string;
  failure_reason_hinglish: string | null;
  is_dry_run: boolean;
}

export interface LiveOrderRequestBody {
  strategy_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price?: number | null;
  dry_run: boolean;
  exchange?: string;
  product_type?: string;
}

// ── Component ──────────────────────────────────────────────────────────

interface GoLiveModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyId: string;
  strategyName: string;
  preflight: SafetyChainResult | null;
  onResult: (result: LiveOrderResult) => void;
}

export function GoLiveModal({
  open,
  onOpenChange,
  strategyId,
  strategyName,
  preflight,
  onResult,
}: GoLiveModalProps) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState<string>("1");
  const [price, setPrice] = useState<string>("");
  const [dryRun, setDryRun] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const symbolValid = symbol.trim().length > 0;
  const quantityValid = !isNaN(Number(quantity)) && Number(quantity) > 0;
  const priceValid =
    price.trim() === "" || (!isNaN(Number(price)) && Number(price) > 0);
  const formValid = symbolValid && quantityValid && priceValid && !submitting;

  async function handleSubmit() {
    if (!formValid) return;
    setSubmitting(true);
    try {
      const body: LiveOrderRequestBody = {
        strategy_id: strategyId,
        symbol: symbol.trim().toUpperCase(),
        side,
        quantity: Number(quantity),
        price: price.trim() === "" ? null : Number(price),
        dry_run: dryRun,
      };
      const result = await api.post<LiveOrderResult>(
        "/orders/live",
        body,
      );
      onResult(result);
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        // Structured 403 — the detail body carries the full
        // LiveOrderResult shape from the backend; surface via
        // onResult so the parent renders a result card.
        const data = err.data as { detail?: LiveOrderResult } | undefined;
        const blockedResult = data?.detail;
        if (blockedResult && typeof blockedResult === "object") {
          onResult(blockedResult);
          onOpenChange(false);
          return;
        }
        toast.error(err.detail);
      } else if (err instanceof ApiError && err.status === 503) {
        toast.error(
          err.detail ||
            "Broker offline hai abhi — kuch der baad try karo.",
        );
      } else if (err instanceof ApiError) {
        toast.error(err.detail);
      } else {
        toast.error("Order place karne mein dikkat aayi. Refresh karke try karo.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const liveButtonAmountHint =
    !dryRun && quantityValid && priceValid && price.trim() !== ""
      ? ` ₹${(Number(quantity) * Number(price)).toLocaleString("en-IN")}`
      : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-md space-y-3"
      >
        <DialogHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <DialogTitle className="text-base font-semibold flex items-center gap-2">
                {dryRun ? (
                  <FlaskConical className="h-4 w-4 text-accent-blue" />
                ) : (
                  <Rocket className="h-4 w-4 text-pink-500" />
                )}
                Place {dryRun ? "Test" : "Live"} Order
              </DialogTitle>
              <p className="text-xs text-muted-foreground">{strategyName}</p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onOpenChange(false)}
              type="button"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>

        <PreflightSummary preflight={preflight} />

        <div className="grid grid-cols-2 gap-3">
          <Field label="Symbol">
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="NIFTY25JANFUT"
              autoFocus
              autoComplete="off"
              spellCheck={false}
            />
          </Field>
          <Field label="Side">
            <SideToggle side={side} onChange={setSide} />
          </Field>
          <Field label="Quantity">
            <Input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </Field>
          <Field label="Price (optional, market if empty)">
            <Input
              type="number"
              min={0}
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="market"
            />
          </Field>
        </div>

        <DryRunToggle value={dryRun} onChange={setDryRun} />

        {!dryRun ? (
          <div className="rounded-lg bg-loss/10 border border-loss/30 p-2.5 flex items-start gap-2 text-xs text-loss">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              Real money order place hone wala hai. Confirm ke baad cancel
              karne ke liye Brokers page se manual cancel karna padega.
            </p>
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-2 pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            type="button"
          >
            Cancel
          </Button>
          <motion.button
            whileHover={formValid ? { scale: 1.02 } : undefined}
            whileTap={formValid ? { scale: 0.98 } : undefined}
            disabled={!formValid}
            onClick={handleSubmit}
            type="button"
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-semibold text-white inline-flex items-center gap-1.5",
              "transition-all duration-200",
              "disabled:cursor-not-allowed disabled:opacity-50",
              dryRun
                ? "bg-gradient-to-r from-accent-blue to-accent-purple"
                : "bg-gradient-to-r from-red-500 to-loss",
            )}
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : dryRun ? (
              <FlaskConical className="h-3.5 w-3.5" />
            ) : (
              <Rocket className="h-3.5 w-3.5" />
            )}
            {submitting
              ? "Order place ho raha hai…"
              : dryRun
                ? "🧪 Test Order"
                : `⚠️ Place Live Order${liveButtonAmountHint}`}
          </motion.button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Sub-pieces ─────────────────────────────────────────────────────────

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function SideToggle({
  side,
  onChange,
}: {
  side: "BUY" | "SELL";
  onChange: (s: "BUY" | "SELL") => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-1 rounded-lg bg-white/[0.04] p-1 border border-white/[0.06]">
      {(["BUY", "SELL"] as const).map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={cn(
            "rounded-md py-1 text-xs font-semibold uppercase transition-colors",
            side === opt
              ? opt === "BUY"
                ? "bg-profit/20 text-profit"
                : "bg-loss/20 text-loss"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function DryRunToggle({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2 flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors",
          value ? "bg-accent-blue" : "bg-loss",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
            value ? "translate-x-0.5" : "translate-x-[1.125rem]",
          )}
        />
      </button>
      <div className="text-xs leading-tight">
        <div className="font-medium">
          {value
            ? "Dry-run mode (test, no real order)"
            : "Live mode (real money)"}
        </div>
        <div className="text-[10px] text-muted-foreground">
          {value
            ? "Safety checks chalenge but broker call skip hoga."
            : "⚠️ Broker ko real order jayega. Sure ho?"}
        </div>
      </div>
    </div>
  );
}

function PreflightSummary({
  preflight,
}: {
  preflight: SafetyChainResult | null;
}) {
  if (!preflight) {
    return (
      <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-2 text-xs text-muted-foreground">
        Pre-flight load ho raha hai…
      </div>
    );
  }
  if (preflight.all_passed) {
    return (
      <div className="rounded-lg bg-profit/10 border border-profit/25 p-2 flex items-center gap-2 text-xs text-profit">
        <span>🛡️</span>
        <span>Saari 7 safety checks pass — order ready hai.</span>
      </div>
    );
  }
  return (
    <div className="rounded-lg bg-loss/10 border border-loss/30 p-2 flex items-start gap-2 text-xs text-loss">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
      <div className="space-y-1">
        <div className="font-medium">Safety check fail hai</div>
        <Badge className="bg-loss/20 text-loss border-loss/30 text-[10px]">
          {preflight.blocking_check?.check_name ?? "unknown"}
        </Badge>
        <p className="leading-relaxed">
          {preflight.blocking_check?.reason_hinglish ??
            "Pre-flight panel mein dekho kya issue hai."}
        </p>
      </div>
    </div>
  );
}
