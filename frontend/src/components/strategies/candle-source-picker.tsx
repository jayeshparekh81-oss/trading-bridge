"use client";

import { useId } from "react";
import { CandlestickChart, Database, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Autocomplete } from "@/components/ui/autocomplete";
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
 *  server-side. Future: ``GET /api/data-provider/symbols``.
 *
 *  Shape: ``{ label, symbol }`` so the datalist can show a friendly
 *  display label ("Nifty Next 50", "Reliance Industries") while
 *  emitting the canonical Dhan trading symbol ("NIFTY NEXT 50",
 *  "RELIANCE") to the backtest request.
 *
 *  Step 1/5 v2 — coordinated with backend ``KNOWN_SYMBOLS`` in
 *  ``backend/app/strategy_engine/data_provider/constants.py``. Every
 *  ``symbol`` value below must have a matching entry there (or an
 *  alias) or the backend's ``_resolve_symbol`` raises ValueError →
 *  uncaught 500.
 *
 *  Backward-compat invariant — NON-NEGOTIABLE: all ten pre-existing
 *  symbol strings remain byte-identical so previously-saved strategies
 *  resolve unchanged:
 *    NIFTY, BANKNIFTY, FINNIFTY,
 *    RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, AXISBANK, ITC.
 *
 *  Three logical groups: F&O NSE indices, F&O BSE indices, large-cap
 *  cash equities. Broader equity expansion is queued for Steps 3-5.
 *  Sectoral / spot-only indices (Nifty IT, Auto, Pharma, etc.) are
 *  intentionally excluded — they have no F&O contracts on either
 *  exchange and live data is not yet wired for them.
 */
export const KNOWN_SYMBOLS: ReadonlyArray<{ label: string; symbol: string }> = [
  // ── F&O indices (7) ─ NSE: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY,
  //    BSE: SENSEX/BANKEX/SNSX50. Nifty Next 50 (sec_id 38) is
  //    intentionally absent — Dhan rejects the historical-data
  //    triple with HTTP 400; see ``docs/POST_LAUNCH_TECH_DEBT.md``.
  { label: "Nifty 50", symbol: "NIFTY" },
  { label: "Bank Nifty", symbol: "BANKNIFTY" },
  { label: "Fin Nifty", symbol: "FINNIFTY" },
  { label: "Nifty Midcap Select", symbol: "MIDCPNIFTY" },
  { label: "Sensex", symbol: "SENSEX" },
  { label: "Bankex", symbol: "BANKEX" },
  { label: "Sensex 50", symbol: "SNSX50" },
  // ── F&O stocks (209, alphabetical) — Step 3. The 7 historical
  //    large-caps preserve their existing display labels (RELIANCE
  //    → "Reliance Industries" etc.); the remaining 202 default to
  //    label=symbol. Regenerated from Dhan scrip-master — see
  //    ``backend/.../constants.py`` docblock for the filter and
  //    regeneration command, kept in lockstep with backend
  //    ``KNOWN_SYMBOLS``.
  { label: "360ONE", symbol: "360ONE" },
  { label: "ABB", symbol: "ABB" },
  { label: "ABCAPITAL", symbol: "ABCAPITAL" },
  { label: "ADANIENSOL", symbol: "ADANIENSOL" },
  { label: "ADANIENT", symbol: "ADANIENT" },
  { label: "ADANIGREEN", symbol: "ADANIGREEN" },
  { label: "ADANIPORTS", symbol: "ADANIPORTS" },
  { label: "ADANIPOWER", symbol: "ADANIPOWER" },
  { label: "ALKEM", symbol: "ALKEM" },
  { label: "AMBER", symbol: "AMBER" },
  { label: "AMBUJACEM", symbol: "AMBUJACEM" },
  { label: "ANGELONE", symbol: "ANGELONE" },
  { label: "APLAPOLLO", symbol: "APLAPOLLO" },
  { label: "APOLLOHOSP", symbol: "APOLLOHOSP" },
  { label: "ASHOKLEY", symbol: "ASHOKLEY" },
  { label: "ASIANPAINT", symbol: "ASIANPAINT" },
  { label: "ASTRAL", symbol: "ASTRAL" },
  { label: "AUBANK", symbol: "AUBANK" },
  { label: "AUROPHARMA", symbol: "AUROPHARMA" },
  { label: "Axis Bank", symbol: "AXISBANK" },
  { label: "BAJAJ-AUTO", symbol: "BAJAJ-AUTO" },
  { label: "BAJAJFINSV", symbol: "BAJAJFINSV" },
  { label: "BAJAJHLDNG", symbol: "BAJAJHLDNG" },
  { label: "BAJFINANCE", symbol: "BAJFINANCE" },
  { label: "BANDHANBNK", symbol: "BANDHANBNK" },
  { label: "BANKBARODA", symbol: "BANKBARODA" },
  { label: "BANKINDIA", symbol: "BANKINDIA" },
  { label: "BDL", symbol: "BDL" },
  { label: "BEL", symbol: "BEL" },
  { label: "BHARATFORG", symbol: "BHARATFORG" },
  { label: "BHARTIARTL", symbol: "BHARTIARTL" },
  { label: "BHEL", symbol: "BHEL" },
  { label: "BIOCON", symbol: "BIOCON" },
  { label: "BLUESTARCO", symbol: "BLUESTARCO" },
  { label: "BOSCHLTD", symbol: "BOSCHLTD" },
  { label: "BPCL", symbol: "BPCL" },
  { label: "BRITANNIA", symbol: "BRITANNIA" },
  { label: "BSE", symbol: "BSE" },
  { label: "CAMS", symbol: "CAMS" },
  { label: "CANBK", symbol: "CANBK" },
  { label: "CDSL", symbol: "CDSL" },
  { label: "CGPOWER", symbol: "CGPOWER" },
  { label: "CHOLAFIN", symbol: "CHOLAFIN" },
  { label: "CIPLA", symbol: "CIPLA" },
  { label: "COALINDIA", symbol: "COALINDIA" },
  { label: "COCHINSHIP", symbol: "COCHINSHIP" },
  { label: "COFORGE", symbol: "COFORGE" },
  { label: "COLPAL", symbol: "COLPAL" },
  { label: "CONCOR", symbol: "CONCOR" },
  { label: "CROMPTON", symbol: "CROMPTON" },
  { label: "CUMMINSIND", symbol: "CUMMINSIND" },
  { label: "DABUR", symbol: "DABUR" },
  { label: "DALBHARAT", symbol: "DALBHARAT" },
  { label: "DELHIVERY", symbol: "DELHIVERY" },
  { label: "DIVISLAB", symbol: "DIVISLAB" },
  { label: "DIXON", symbol: "DIXON" },
  { label: "DLF", symbol: "DLF" },
  { label: "DMART", symbol: "DMART" },
  { label: "DRREDDY", symbol: "DRREDDY" },
  { label: "EICHERMOT", symbol: "EICHERMOT" },
  { label: "ETERNAL", symbol: "ETERNAL" },
  { label: "EXIDEIND", symbol: "EXIDEIND" },
  { label: "FEDERALBNK", symbol: "FEDERALBNK" },
  { label: "FORCEMOT", symbol: "FORCEMOT" },
  { label: "FORTIS", symbol: "FORTIS" },
  { label: "GAIL", symbol: "GAIL" },
  { label: "GLENMARK", symbol: "GLENMARK" },
  { label: "GMRAIRPORT", symbol: "GMRAIRPORT" },
  { label: "GODFRYPHLP", symbol: "GODFRYPHLP" },
  { label: "GODREJCP", symbol: "GODREJCP" },
  { label: "GODREJPROP", symbol: "GODREJPROP" },
  { label: "GRASIM", symbol: "GRASIM" },
  { label: "HAL", symbol: "HAL" },
  { label: "HAVELLS", symbol: "HAVELLS" },
  { label: "HCLTECH", symbol: "HCLTECH" },
  { label: "HDFCAMC", symbol: "HDFCAMC" },
  { label: "HDFC Bank", symbol: "HDFCBANK" },
  { label: "HDFCLIFE", symbol: "HDFCLIFE" },
  { label: "HEROMOTOCO", symbol: "HEROMOTOCO" },
  { label: "HINDALCO", symbol: "HINDALCO" },
  { label: "HINDPETRO", symbol: "HINDPETRO" },
  { label: "HINDUNILVR", symbol: "HINDUNILVR" },
  { label: "HINDZINC", symbol: "HINDZINC" },
  { label: "HYUNDAI", symbol: "HYUNDAI" },
  { label: "ICICI Bank", symbol: "ICICIBANK" },
  { label: "ICICIGI", symbol: "ICICIGI" },
  { label: "ICICIPRULI", symbol: "ICICIPRULI" },
  { label: "IDEA", symbol: "IDEA" },
  { label: "IDFCFIRSTB", symbol: "IDFCFIRSTB" },
  { label: "IEX", symbol: "IEX" },
  { label: "INDHOTEL", symbol: "INDHOTEL" },
  { label: "INDIANB", symbol: "INDIANB" },
  { label: "INDIGO", symbol: "INDIGO" },
  { label: "INDUSINDBK", symbol: "INDUSINDBK" },
  { label: "INDUSTOWER", symbol: "INDUSTOWER" },
  { label: "Infosys", symbol: "INFY" },
  { label: "INOXWIND", symbol: "INOXWIND" },
  { label: "IOC", symbol: "IOC" },
  { label: "IREDA", symbol: "IREDA" },
  { label: "IRFC", symbol: "IRFC" },
  { label: "ITC", symbol: "ITC" },
  { label: "JINDALSTEL", symbol: "JINDALSTEL" },
  { label: "JIOFIN", symbol: "JIOFIN" },
  { label: "JSWENERGY", symbol: "JSWENERGY" },
  { label: "JSWSTEEL", symbol: "JSWSTEEL" },
  { label: "JUBLFOOD", symbol: "JUBLFOOD" },
  { label: "KALYANKJIL", symbol: "KALYANKJIL" },
  { label: "KAYNES", symbol: "KAYNES" },
  { label: "KEI", symbol: "KEI" },
  { label: "KFINTECH", symbol: "KFINTECH" },
  { label: "KOTAKBANK", symbol: "KOTAKBANK" },
  { label: "KPITTECH", symbol: "KPITTECH" },
  { label: "LAURUSLABS", symbol: "LAURUSLABS" },
  { label: "LICHSGFIN", symbol: "LICHSGFIN" },
  { label: "LICI", symbol: "LICI" },
  { label: "LODHA", symbol: "LODHA" },
  { label: "LT", symbol: "LT" },
  { label: "LTF", symbol: "LTF" },
  { label: "LTM", symbol: "LTM" },
  { label: "LUPIN", symbol: "LUPIN" },
  { label: "M&M", symbol: "M&M" },
  { label: "MANAPPURAM", symbol: "MANAPPURAM" },
  { label: "MANKIND", symbol: "MANKIND" },
  { label: "MARICO", symbol: "MARICO" },
  { label: "MARUTI", symbol: "MARUTI" },
  { label: "MAXHEALTH", symbol: "MAXHEALTH" },
  { label: "MAZDOCK", symbol: "MAZDOCK" },
  { label: "MCX", symbol: "MCX" },
  { label: "MFSL", symbol: "MFSL" },
  { label: "MOTHERSON", symbol: "MOTHERSON" },
  { label: "MOTILALOFS", symbol: "MOTILALOFS" },
  { label: "MPHASIS", symbol: "MPHASIS" },
  { label: "MUTHOOTFIN", symbol: "MUTHOOTFIN" },
  { label: "NAM-INDIA", symbol: "NAM-INDIA" },
  { label: "NATIONALUM", symbol: "NATIONALUM" },
  { label: "NAUKRI", symbol: "NAUKRI" },
  { label: "NBCC", symbol: "NBCC" },
  { label: "NESTLEIND", symbol: "NESTLEIND" },
  { label: "NHPC", symbol: "NHPC" },
  { label: "NMDC", symbol: "NMDC" },
  { label: "NTPC", symbol: "NTPC" },
  { label: "NUVAMA", symbol: "NUVAMA" },
  { label: "NYKAA", symbol: "NYKAA" },
  { label: "OBEROIRLTY", symbol: "OBEROIRLTY" },
  { label: "OFSS", symbol: "OFSS" },
  { label: "OIL", symbol: "OIL" },
  { label: "ONGC", symbol: "ONGC" },
  { label: "PAGEIND", symbol: "PAGEIND" },
  { label: "PATANJALI", symbol: "PATANJALI" },
  { label: "PAYTM", symbol: "PAYTM" },
  { label: "PERSISTENT", symbol: "PERSISTENT" },
  { label: "PETRONET", symbol: "PETRONET" },
  { label: "PFC", symbol: "PFC" },
  { label: "PGEL", symbol: "PGEL" },
  { label: "PHOENIXLTD", symbol: "PHOENIXLTD" },
  { label: "PIDILITIND", symbol: "PIDILITIND" },
  { label: "PIIND", symbol: "PIIND" },
  { label: "PNB", symbol: "PNB" },
  { label: "PNBHOUSING", symbol: "PNBHOUSING" },
  { label: "POLICYBZR", symbol: "POLICYBZR" },
  { label: "POLYCAB", symbol: "POLYCAB" },
  { label: "POWERGRID", symbol: "POWERGRID" },
  { label: "POWERINDIA", symbol: "POWERINDIA" },
  { label: "PREMIERENE", symbol: "PREMIERENE" },
  { label: "PRESTIGE", symbol: "PRESTIGE" },
  { label: "RBLBANK", symbol: "RBLBANK" },
  { label: "RECLTD", symbol: "RECLTD" },
  { label: "Reliance Industries", symbol: "RELIANCE" },
  { label: "RVNL", symbol: "RVNL" },
  { label: "SAIL", symbol: "SAIL" },
  { label: "SAMMAANCAP", symbol: "SAMMAANCAP" },
  { label: "SBICARD", symbol: "SBICARD" },
  { label: "SBILIFE", symbol: "SBILIFE" },
  { label: "SBIN", symbol: "SBIN" },
  { label: "SHREECEM", symbol: "SHREECEM" },
  { label: "SHRIRAMFIN", symbol: "SHRIRAMFIN" },
  { label: "SIEMENS", symbol: "SIEMENS" },
  { label: "SOLARINDS", symbol: "SOLARINDS" },
  { label: "SONACOMS", symbol: "SONACOMS" },
  { label: "SRF", symbol: "SRF" },
  { label: "SUNPHARMA", symbol: "SUNPHARMA" },
  { label: "SUPREMEIND", symbol: "SUPREMEIND" },
  { label: "SUZLON", symbol: "SUZLON" },
  { label: "SWIGGY", symbol: "SWIGGY" },
  { label: "TATACONSUM", symbol: "TATACONSUM" },
  { label: "TATAELXSI", symbol: "TATAELXSI" },
  { label: "TATAPOWER", symbol: "TATAPOWER" },
  { label: "TATASTEEL", symbol: "TATASTEEL" },
  { label: "TCS", symbol: "TCS" },
  { label: "TECHM", symbol: "TECHM" },
  { label: "TIINDIA", symbol: "TIINDIA" },
  { label: "TITAN", symbol: "TITAN" },
  { label: "TMPV", symbol: "TMPV" },
  { label: "TORNTPHARM", symbol: "TORNTPHARM" },
  { label: "TRENT", symbol: "TRENT" },
  { label: "TVSMOTOR", symbol: "TVSMOTOR" },
  { label: "ULTRACEMCO", symbol: "ULTRACEMCO" },
  { label: "UNIONBANK", symbol: "UNIONBANK" },
  { label: "UNITDSPR", symbol: "UNITDSPR" },
  { label: "UNOMINDA", symbol: "UNOMINDA" },
  { label: "UPL", symbol: "UPL" },
  { label: "VBL", symbol: "VBL" },
  { label: "VEDL", symbol: "VEDL" },
  { label: "VMM", symbol: "VMM" },
  { label: "VOLTAS", symbol: "VOLTAS" },
  { label: "WAAREEENER", symbol: "WAAREEENER" },
  { label: "WIPRO", symbol: "WIPRO" },
  { label: "YESBANK", symbol: "YESBANK" },
  { label: "ZYDUSLIFE", symbol: "ZYDUSLIFE" },
] as const;

/** Adapter for ``components/ui/autocomplete`` which expects ``value``
 *  (not ``symbol``) as the canonical-id field. KNOWN_SYMBOLS keeps the
 *  ``symbol`` name for backwards compat with its existing public
 *  shape; this private constant transforms it once at module load. */
const AUTOCOMPLETE_ITEMS: ReadonlyArray<{ label: string; value: string }> =
  KNOWN_SYMBOLS.map((s) => ({ label: s.label, value: s.symbol }));

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
  const fromInputId = useId();
  const toInputId = useId();
  const symbolInputId = useId();
  const timeframeInputId = useId();

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <FormField label="Symbol" htmlFor={symbolInputId}>
          {/* Base UI Autocomplete (Step 3) — replaces the native
              ``<datalist>`` which became qualitatively broken on
              mobile at this scale (216 entries). Free-text fallback
              is preserved: ``onValueChange`` fires on every keystroke,
              including non-matching values, and the backend's
              normalise_symbol resolves them via canonical + alias map.
              The ``.toUpperCase()`` mirrors the original input's
              keystroke handler — backend-side resolution is case-
              insensitive, but uppercased values match the canonical
              KNOWN_SYMBOLS keys directly without going through the
              alias path. */}
          <Autocomplete
            id={symbolInputId}
            value={request.symbol}
            onValueChange={(value) =>
              onChange({ symbol: value.toUpperCase() })
            }
            items={AUTOCOMPLETE_ITEMS}
            placeholder="Type to search 216 symbols…"
          />
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
          ? "Server-side symbol resolution — pick from the autocomplete or type freely."
          : "Autocomplete covers 216 F&O indices and stocks (e.g., NIFTY, BANKNIFTY, RELIANCE, TCS, INFY). " +
            "Free-text input is allowed — the server resolves via canonical / alias map. " +
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

