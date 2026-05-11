"use client";

import { useId } from "react";
import { CandlestickChart, Database, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Candle source picker — used by Phase 5 builders and the backtest
 * result page. State is controlled so callers persist it through
 * navigation (typically via ``localStorage`` between the builder and
 * the backtest result page).
 */

export type CandleSource = "synthetic" | "dhan_historical";
export type CandleTimeframe = "1m" | "5m" | "15m" | "1h" | "1d";

/** Wire shape expected by ``POST /strategies/{id}/backtest`` body. */
export interface CandlesRequestPayload {
  symbol: string;
  timeframe: CandleTimeframe;
  from_date: string; // ISO 8601 UTC
  to_date: string; // ISO 8601 UTC
}

export interface CandleSourcePickerValue {
  source: CandleSource;
  /** Filled only when ``source === "dhan_historical"``. */
  candles_request: CandlesRequestPayload | null;
  /** Local validation error (e.g., from > to). Empty string when ok. */
  validation_error: string;
}

interface Props {
  value: CandleSourcePickerValue;
  onChange: (value: CandleSourcePickerValue) => void;
  /** When ``true`` the picker hides the "Synthetic" toggle and shows
   * only the Dhan form. The beginner builder skips the picker entirely
   * — this prop is for the backtest page where the user has already
   * opted into a real-data re-run. */
  forceDhan?: boolean;
  /** When ``true``, render a compact hint that the symbol list is
   * the bundled subset (used inside dialogs to keep the chrome
   * minimal). */
  compactHint?: boolean;
}

/** Hard-coded sample of the symbols the Phase B adapter resolves
 * server-side. Future: ``GET /api/data-provider/symbols``. */
export const KNOWN_SYMBOLS: readonly string[] = [
  "NIFTY",
  "BANKNIFTY",
  "FINNIFTY",
  "RELIANCE",
  "TCS",
  "INFY",
  "HDFCBANK",
  "ICICIBANK",
  "AXISBANK",
  "ITC",
] as const;

const TIMEFRAMES: readonly CandleTimeframe[] = ["1m", "5m", "15m", "1h", "1d"] as const;

/** Build a sensible default Dhan request — last 90 days at 5m. */
export function defaultCandlesRequest(): CandlesRequestPayload {
  const now = new Date();
  const ninetyDaysAgo = new Date(now);
  ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 89);
  return {
    symbol: "NIFTY",
    timeframe: "5m",
    from_date: ninetyDaysAgo.toISOString(),
    to_date: now.toISOString(),
  };
}

/** Default value for first render. ``defaultSource`` lets each
 * builder pre-select Synthetic (intermediate) or Real Dhan (expert). */
export function makeDefaultPickerValue(
  defaultSource: CandleSource = "synthetic",
): CandleSourcePickerValue {
  return {
    source: defaultSource,
    candles_request:
      defaultSource === "dhan_historical" ? defaultCandlesRequest() : null,
    validation_error: "",
  };
}

export function CandleSourcePicker({
  value,
  onChange,
  forceDhan = false,
  compactHint = false,
}: Props) {
  const headingId = useId();

  const handleSourceChange = (next: CandleSource) => {
    if (next === "dhan_historical") {
      onChange({
        source: "dhan_historical",
        candles_request: value.candles_request ?? defaultCandlesRequest(),
        validation_error: "",
      });
    } else {
      onChange({ source: "synthetic", candles_request: null, validation_error: "" });
    }
  };

  const handleRequestChange = (
    next: Partial<CandlesRequestPayload>,
  ) => {
    const merged: CandlesRequestPayload = {
      ...(value.candles_request ?? defaultCandlesRequest()),
      ...next,
    };
    onChange({
      source: "dhan_historical",
      candles_request: merged,
      validation_error: validateRequest(merged),
    });
  };

  const showDhanForm =
    forceDhan || value.source === "dhan_historical";

  return (
    <GlassmorphismCard hover={false} className="space-y-3">
      <div className="flex items-center gap-2">
        <CandlestickChart className="h-4 w-4 text-accent-blue" aria-hidden />
        <h3 id={headingId} className="text-sm font-semibold">
          Candle source
        </h3>
        {forceDhan ? null : (
          <Badge className="ml-auto text-[10px] bg-white/[0.06] border-white/[0.1]">
            backtest data
          </Badge>
        )}
      </div>

      {forceDhan ? null : (
        <SourceToggle source={value.source} onChange={handleSourceChange} />
      )}

      {showDhanForm ? (
        <DhanForm
          request={value.candles_request ?? defaultCandlesRequest()}
          onChange={handleRequestChange}
          validationError={value.validation_error}
          compactHint={compactHint}
        />
      ) : (
        <SyntheticHint />
      )}
    </GlassmorphismCard>
  );
}

// ─── Source toggle ─────────────────────────────────────────────────────

function SourceToggle({
  source,
  onChange,
}: {
  source: CandleSource;
  onChange: (next: CandleSource) => void;
}) {
  return (
    <div role="tablist" aria-label="Candle source" className="grid grid-cols-2 gap-2">
      <ToggleButton
        active={source === "synthetic"}
        onClick={() => onChange("synthetic")}
        icon={Sparkles}
        label="Synthetic"
        sub="Quick test (120 bars)"
      />
      <ToggleButton
        active={source === "dhan_historical"}
        onClick={() => onChange("dhan_historical")}
        icon={Database}
        label="Real Dhan data"
        sub="Pull from your subscription"
      />
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  icon: Icon,
  label,
  sub,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  sub: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
        active
          ? "border-accent-blue/40 bg-accent-blue/[0.08]"
          : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04]",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 mt-0.5",
          active ? "text-accent-blue" : "text-muted-foreground",
        )}
      />
      <div className="space-y-0.5">
        <div
          className={cn("text-xs font-medium", active ? "text-accent-blue" : "")}
        >
          {label}
        </div>
        <div className="text-[10px] text-muted-foreground">{sub}</div>
      </div>
    </button>
  );
}

// ─── Synthetic hint ────────────────────────────────────────────────────

function SyntheticHint() {
  return (
    <p className="text-[12px] text-muted-foreground leading-snug">
      120-bar deterministic series. Fast and reproducible — best for
      sanity-checking strategy logic before pulling real data.
    </p>
  );
}

// ─── Dhan form ─────────────────────────────────────────────────────────

function DhanForm({
  request,
  onChange,
  validationError,
  compactHint,
}: {
  request: CandlesRequestPayload;
  onChange: (next: Partial<CandlesRequestPayload>) => void;
  validationError: string;
  compactHint: boolean;
}) {
  const symbolListId = useId();
  const fromInputId = useId();
  const toInputId = useId();
  const symbolInputId = useId();
  const timeframeInputId = useId();

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <FormField label="Symbol" htmlFor={symbolInputId}>
          <input
            id={symbolInputId}
            type="text"
            list={symbolListId}
            value={request.symbol}
            onChange={(e) => onChange({ symbol: e.target.value.toUpperCase() })}
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          />
          <datalist id={symbolListId}>
            {KNOWN_SYMBOLS.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </FormField>

        <FormField label="Timeframe" htmlFor={timeframeInputId}>
          <select
            id={timeframeInputId}
            value={request.timeframe}
            onChange={(e) =>
              onChange({ timeframe: e.target.value as CandleTimeframe })
            }
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <FormField label="From (UTC)" htmlFor={fromInputId}>
          <input
            id={fromInputId}
            type="datetime-local"
            value={toLocalInput(request.from_date)}
            onChange={(e) => onChange({ from_date: fromLocalInput(e.target.value) })}
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          />
        </FormField>
        <FormField label="To (UTC)" htmlFor={toInputId}>
          <input
            id={toInputId}
            type="datetime-local"
            value={toLocalInput(request.to_date)}
            onChange={(e) => onChange({ to_date: fromLocalInput(e.target.value) })}
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          />
        </FormField>
      </div>

      {validationError ? (
        <p className="text-[11px] text-loss leading-snug">{validationError}</p>
      ) : null}

      <p className="text-[11px] text-muted-foreground leading-snug">
        {compactHint
          ? "Server-side symbol resolution — pick from the autocomplete."
          : "Symbol autocomplete uses the bundled list (NIFTY, BANKNIFTY, …). " +
            "Real-data fetches require ``DHAN_ACCESS_TOKEN`` configured server-side."}
      </p>
    </div>
  );
}

function FormField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

// ─── Beginner-mode hint card ──────────────────────────────────────────

export function BeginnerSyntheticHint() {
  return (
    <div className="rounded-md border border-white/[0.08] bg-white/[0.02] p-3 flex items-start gap-2">
      <Sparkles className="h-4 w-4 text-accent-blue mt-0.5 shrink-0" />
      <div className="space-y-0.5">
        <p className="text-xs font-medium">Synthetic data</p>
        <p className="text-[11px] text-muted-foreground leading-snug">
          Backtest synthetic 120-bar series par chalega — beginner mode mein
          yeh default hai. Real market data se backtest karne ke liye
          Intermediate ya Expert mode use karo.
        </p>
      </div>
    </div>
  );
}

// ─── Validation + storage helpers (exported for builders) ─────────────

/** Returns a Hinglish error string, or empty string if valid. */
export function validateRequest(req: CandlesRequestPayload): string {
  if (!req.symbol.trim()) return "Symbol khaali nahi ho sakta.";
  const from = new Date(req.from_date);
  const to = new Date(req.to_date);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return "Date format galat hai.";
  }
  if (from >= to) return "From date To date se chhoti honi chahiye.";
  if (req.timeframe !== "1d") {
    const days = (to.getTime() - from.getTime()) / 86_400_000;
    if (days > 90) return "Intraday window 90 din se zyada nahi ho sakti.";
  }
  return "";
}

const STORAGE_KEY = "tradetri:next_candles_request";

/** Stash a request for the next backtest page mount to consume. */
export function stashCandlesRequest(value: CandleSourcePickerValue): void {
  if (typeof window === "undefined") return;
  if (
    value.source !== "dhan_historical"
    || value.candles_request === null
    || value.validation_error !== ""
  ) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value.candles_request));
}

/** Read and clear the stashed request — one-shot consume. */
export function consumeStashedCandlesRequest(): CandlesRequestPayload | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  window.localStorage.removeItem(STORAGE_KEY);
  try {
    const parsed = JSON.parse(raw) as CandlesRequestPayload;
    if (
      typeof parsed.symbol !== "string"
      || typeof parsed.timeframe !== "string"
      || typeof parsed.from_date !== "string"
      || typeof parsed.to_date !== "string"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

// ─── Local-input ↔ ISO conversion ─────────────────────────────────────

/** ``2026-04-07T15:30:00Z`` → ``2026-04-07T15:30`` (HTML datetime-local). */
function toLocalInput(iso: string): string {
  try {
    return iso.slice(0, 16);
  } catch {
    return "";
  }
}

/** ``2026-04-07T15:30`` (datetime-local) → ``2026-04-07T15:30:00Z``. */
function fromLocalInput(local: string): string {
  if (!local) return new Date().toISOString();
  return new Date(local + ":00Z").toISOString();
}

