"use client";

/**
 * VehiclePicker — the five vehicles, the measured capital line, and the
 * ATM/OTM/ITM choice. Phone-first: one column, big tap targets, ONE next step.
 *
 * HONESTY MECHANICS (each asserted by tests/marketplace/vehicle-picker.test.tsx):
 *   - Only vehicles the backend marks `visible` are rendered; with every flag OFF
 *     that is FUTURES alone (the launch rule).
 *   - A locked vehicle shows the sentence it is WAITING FOR, never "coming soon"
 *     and never a number.
 *   - Every capital figure is rendered WITH its basis sentence; a NOT MEASURED
 *     figure renders the literal — never 0, never a dash.
 *   - OTM is pre-selected and labelled as the recommended default; a win rate is
 *     shown only beside a measured drawdown (winRateBesideDrawdown).
 *   - Three states: loading / empty / error are each rendered; nothing falls back
 *     to fabricated data.
 *
 * ONE SOURCE PER FACT: every number comes from the flag-gated backend surface;
 * this component owns copy and layout only.
 */

import { useState } from "react";
import { Lock } from "lucide-react";
import { useApi } from "@/shared/api/use-api";
import { formatCurrency } from "@/shared/lib/utils";
import { cn } from "@/shared/lib/utils";
import {
  DEFAULT_MONEYNESS,
  VEHICLE_PLAIN,
  VEHICLE_SEGMENT,
  cell,
  defaultFirst,
  lockLine,
  winRateBesideDrawdown,
  type CapitalLine,
  type CustomerVehicle,
  type Moneyness,
  type MoneynessTable,
  type VehicleBoard,
  type VehicleStatus,
} from "@/lib/customer-vehicles";
import {
  NOT_MEASURED,
  SEGMENT_MIN_CAPITAL,
  SEGMENT_RISK,
  SEGMENT_WORST_DAY,
  formatCapital,
} from "@/lib/risk-labels";
import { RiskLegend } from "@/components/risk/risk-chip";
import {
  DIRECTION_CHOICES,
  FUTURES_LOT_CHOICES,
  barLines,
  groupIntoCards,
  paperProgress,
  staticMoneynessTable,
  staticVehicleBoard,
  vehiclePickerSource,
  type PickerSource,
} from "@/lib/vehicle-cards";

interface Props {
  /** Even lots the customer chose; drives the capital line. */
  lots: number;
  /** Called when the customer taps a vehicle (locked ones included — the choice is theirs). */
  onVehicle?: (v: CustomerVehicle) => void;
  onMoneyness?: (m: Moneyness) => void;
  className?: string;
  /** "static" = the generated four-card board, no server call (before the backend
   * surface is deployed); default from NEXT_PUBLIC_VEHICLE_PICKER_SOURCE, else live. */
  source?: PickerSource;
  /** ONE LINE per vehicle (founder, 26 Sep: "what it needs, its risk label, and the
   * worst real day in rupees"); every other word behind a collapsed "Aur jaano". */
  compact?: boolean;
}

const rupees = (n: number) => formatCurrency(n, { compact: true });
/** Plain words when an older payload carries no `default_basis_hi` (the English founder quote is not customer copy). */
const DEFAULT_BASIS_FALLBACK_HI = "OTM (thoda door wala strike) pehle se chuna hua hai — yeh TRADETRI ka default hai.";

function Figure({ label, value, basis, testId }: { label: string; value: number | string; basis: string; testId: string }) {
  const measured = typeof value === "number";
  return (
    <div data-testid={testId} data-measured={measured ? "true" : "false"} className="py-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn("text-12 font-medium", measured ? "text-foreground" : "text-amber-300")}>
          {measured ? rupees(value) : NOT_MEASURED}
        </span>
      </div>
      {/* the basis is VISIBLE copy, never tooltip-only */}
      <p data-testid={`${testId}-basis`} className="text-xs text-foreground/50 leading-relaxed">
        {basis}
      </p>
    </div>
  );
}

export function CapitalLineCard({ line }: { line: CapitalLine }) {
  return (
    <section data-testid="capital-line" className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="text-xs font-medium text-foreground/90">
        Kitna paisa chahiye — {typeof line.lot_size === "number" ? `${line.lots * line.lot_size} shares` : `${line.lots} packet`} ({line.lots} lot)
      </div>
      <Figure label="Kam se kam kitna paisa (minimum capital)" value={line.minimum_capital.value} basis={line.minimum_capital.basis} testId="capital-minimum" />
      <Figure label="Broker kitna rok ke rakhega (margin, NRML)" value={line.margin.value} basis={line.margin.basis} testId="capital-margin" />
      <Figure label="Sabse bada gir (worst drawdown)" value={line.max_drawdown.value} basis={line.max_drawdown.basis} testId="capital-drawdown" />
      <Figure label="Sabse bura din (worst day)" value={line.worst_day.value} basis={line.worst_day.basis} testId="capital-worst-day" />
      <p className="text-xs text-muted-foreground leading-relaxed mt-1">
        Hisaab ka niyam: {line.rule_text}
      </p>
      {line.margin_stale ? (
        <p data-testid="capital-margin-stale" className="text-xs text-amber-300/80 leading-relaxed mt-1">
          Broker ke rok (margin) ka number {line.margin.as_of ?? "kis din ka — record nahi"} ka hai — 7 din se purana. Broker par aaj ka alag ho sakta hai.
        </p>
      ) : null}
    </section>
  );
}

export function MoneynessPicker({
  table,
  value,
  onChange,
  readOnly = false,
}: {
  table: MoneynessTable;
  value: Moneyness;
  onChange: (m: Moneyness) => void;
  /** C2 (26 Sep): the comparison only — for a vehicle that is still closed, no choice to make yet. */
  readOnly?: boolean;
}) {
  const rows = defaultFirst(table.rows);
  // one id namespace per vehicle so three read-only tables can sit on one screen
  const id = (s: string) => (readOnly ? `${s}-${table.vehicle}` : s);
  if (readOnly) {
    return (
      <section data-testid={id("moneyness-compare")} className="min-w-0 space-y-1.5">
        <div className="wrap-break-word text-xs font-medium text-foreground/90">
          Strike ki tulna: OTM (thoda door wala strike, pehle se chuna hua) · ATM (abhi ke daam wala) · ITM (andar wala)
        </div>
        <MoneynessRows rows={rows} id={id} />
        <p data-testid={id("moneyness-default-basis")} className="wrap-break-word text-xs text-foreground/50 leading-relaxed">
          {table.default_basis_hi ?? DEFAULT_BASIS_FALLBACK_HI}
        </p>
      </section>
    );
  }
  return (
    <section data-testid="moneyness-picker" className="space-y-2">
      <div className="text-xs font-medium text-foreground/90">Strike kaunsa — aapki choice</div>
      <div role="radiogroup" aria-label="Strike" className="grid grid-cols-3 gap-1.5">
        {rows.map((r) => (
          <button
            key={r.moneyness}
            type="button"
            role="radio"
            aria-checked={value === r.moneyness}
            data-testid={`moneyness-${r.moneyness}`}
            data-recommended={r.recommended ? "true" : "false"}
            onClick={() => onChange(r.moneyness)}
            className={cn(
              "min-h-11 rounded-md border px-2 py-1.5 text-12 font-medium",
              value === r.moneyness ? "border-profit/60 bg-profit/10 text-foreground" : "border-white/[0.08] text-foreground/80",
            )}
          >
            {r.moneyness}
            {r.recommended ? (
              <span className="block text-xs uppercase tracking-wide text-profit">Recommended (default)</span>
            ) : null}
          </button>
        ))}
      </div>
      <p data-testid="moneyness-default-basis" className="text-xs text-foreground/50 leading-relaxed">
        {table.default_basis_hi ?? DEFAULT_BASIS_FALLBACK_HI}
      </p>
      {/* the comparison table: net · drawdown · win rate · trades · period, every row */}
      <MoneynessRows rows={rows} id={(s) => s} />
    </section>
  );
}

/** One row per strike. An unmeasured row's trade count is the file's placeholder "0", not data —
 *  it renders NOT MEASURED like every other cell (RULES #50 point 10). */
function MoneynessRows({ rows, id }: { rows: MoneynessTable["rows"]; id: (s: string) => string }) {
  return (
    <ul className="min-w-0 space-y-1.5">
      {rows.map((r) => (
        <li
          key={r.moneyness}
          data-testid={id(`moneyness-row-${r.moneyness}`)}
          data-measured={r.measured ? "true" : "false"}
          className="min-w-0 rounded-md border border-white/[0.06] bg-white/[0.02] p-2 text-xs"
        >
          <div className="flex flex-wrap justify-between gap-x-2 min-w-0">
            <span className="font-medium text-foreground/90">
              {r.moneyness}
              {r.recommended ? " · recommended" : ""}
            </span>
            <span data-testid={id(`moneyness-trades-${r.moneyness}`)} className="wrap-break-word text-muted-foreground">
              {r.measured && typeof r.trades === "number" ? `${r.trades} sauda (trades)` : `Sauda (trades): ${NOT_MEASURED}`}
              {" · "}
              {r.measured ? r.period : `Samay: ${NOT_MEASURED}`}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-0.5 mt-1 min-w-0">
            <span className="wrap-break-word">Kharcha kaat ke munafa (net, Dhan ke bill ke baad): {cell(r.net_after_charges_rupees, rupees)}</span>
            <span className="wrap-break-word">Sabse bada girna (drawdown): {cell(r.worst_drawdown_rupees, rupees)}</span>
            <span className="wrap-break-word">Kitni baar munafa (win rate): {winRateBesideDrawdown(r)}</span>
          </div>
          {r.measured ? <p className="wrap-break-word text-foreground/50 leading-relaxed mt-1">Kahan se: {r.source}</p> : null}
        </li>
      ))}
    </ul>
  );
}

/** The status word on a vehicle, one source for the card and the one-line row. */
function VehicleStatusChip({ v }: { v: VehicleStatus }) {
  if (v.open) return <span className="shrink-0 text-xs uppercase tracking-wide text-profit">Khula hai</span>;
  if (v.selectable)
    return (
      <span data-testid={`vehicle-selectable-${v.vehicle}`} className="shrink-0 text-xs uppercase tracking-wide text-profit">
        Chuno · paper
      </span>
    );
  return (
    <span className="shrink-0 text-xs uppercase tracking-wide text-amber-300 flex items-center gap-1">
      <Lock className="h-3 w-3" aria-hidden /> Band
    </span>
  );
}

/**
 * THE ONE LINE per vehicle (founder, 26 Sep, settings screen point 1): what it needs ·
 * its risk label · the worst real day in rupees, each with its basis marker —
 * "naapa" (measured) or "hamara andaaza" (our judgement). A missing number is the
 * NOT MEASURED literal. Everything else lives behind "Aur jaano".
 */
export function vehicleFacts(v: CustomerVehicle): string {
  const seg = VEHICLE_SEGMENT[v];
  const need = SEGMENT_MIN_CAPITAL[seg];
  const worst = SEGMENT_WORST_DAY[seg];
  const needText =
    need.value == null ? NOT_MEASURED : `${formatCapital(need, formatCurrency)} (2 lot (packet) par, naapa)`;
  const worstText =
    worst.value == null ? `${NOT_MEASURED} (${worst.marker})` : `−${formatCurrency(worst.value)} (${worst.marker})`;
  return `Chahiye: ${needText} · Risk: ${SEGMENT_RISK[seg].level.toUpperCase()} (hamara andaaza) · Sabse bura din: ${worstText}`;
}

function VehicleLine({ v, selected, onSelect }: { v: VehicleStatus; selected: boolean; onSelect: () => void }) {
  const plain = VEHICLE_PLAIN[v.vehicle];
  // A closed vehicle cannot be "chosen": tapping it must not light it up as if it were picked.
  const choosable = v.open || v.selectable === true;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-disabled={choosable ? undefined : true}
      data-testid={`vehicle-line-${v.vehicle}`}
      data-open={v.open ? "true" : "false"}
      onClick={choosable ? onSelect : undefined}
      className={cn(
        "w-full min-w-0 text-left rounded-lg border px-3 py-2.5 min-h-tap",
        selected ? "border-profit/60 bg-profit/10" : "border-white/[0.08] bg-white/[0.02]",
      )}
    >
      <span className="flex items-start justify-between gap-2 min-w-0">
        <span className="min-w-0 wrap-break-word text-sm font-medium text-foreground">{plain.label}</span>
        <VehicleStatusChip v={v} />
      </span>
      <span data-testid={`vehicle-facts-${v.vehicle}`} className="block min-w-0 wrap-break-word text-xs text-foreground/70 leading-relaxed mt-0.5">
        {vehicleFacts(v.vehicle)}
      </span>
    </button>
  );
}

function VehicleCard({
  v,
  selected,
  onSelect,
  asInfo = false,
}: {
  v: VehicleStatus;
  selected: boolean;
  onSelect: () => void;
  /** Read-only copy of the card (inside "Aur jaano"): every word, no second radio. */
  asInfo?: boolean;
}) {
  const plain = VEHICLE_PLAIN[v.vehicle];
  const Tag = asInfo ? "div" : "button";
  return (
    <Tag
      {...(asInfo
        ? { "data-testid": `vehicle-detail-${v.vehicle}` }
        : { type: "button" as const, role: "radio", "aria-checked": selected, "data-testid": `vehicle-card-${v.vehicle}`, onClick: onSelect })}
      data-open={v.open ? "true" : "false"}
      className={cn(
        "w-full min-w-0 text-left rounded-lg border p-3",
        asInfo ? "border-white/[0.06] bg-white/[0.01]" : "min-h-14",
        !asInfo && (selected ? "border-profit/60 bg-profit/10" : "border-white/[0.08] bg-white/[0.02]"),
      )}
    >
      <div className="flex items-center justify-between gap-2 min-w-0">
        <span className="min-w-0 wrap-break-word text-12 font-medium text-foreground">{plain.label}</span>
        <VehicleStatusChip v={v} />
      </div>
      <p className="wrap-break-word text-xs text-muted-foreground leading-relaxed mt-1">{plain.what}</p>
      {v.has_live_record ? (
        <p className="text-xs text-foreground/60 mt-1">Asli live record hai (20 Aug 2026 se).</p>
      ) : null}
      {!v.open ? (
        <p data-testid={asInfo ? `vehicle-detail-waiting-${v.vehicle}` : `vehicle-waiting-${v.vehicle}`} className="wrap-break-word text-xs text-amber-300/80 leading-relaxed mt-1">
          {lockLine(v)}
        </p>
      ) : null}
      {v.vehicle === "FUTURES" ? (
        <p data-testid={asInfo ? "vehicle-detail-futures-choices" : "vehicle-futures-choices"} className="wrap-break-word text-xs text-foreground/60 leading-relaxed mt-1">
          Lots: {FUTURES_LOT_CHOICES.join(" · ")} · Direction: {DIRECTION_CHOICES.map((d) => d.label).join(" / ")}
        </p>
      ) : null}
      {!v.open && v.vehicle !== "FUTURES" && barLines(v).length ? (
        <div data-testid={asInfo ? `vehicle-detail-bar-${v.vehicle}` : `vehicle-bar-${v.vehicle}`} className="mt-1.5 min-w-0 rounded-md border border-white/[0.06] p-2">
          <p className="text-xs font-medium text-foreground/80">Iska evidence bar (24 Sep ko seal hua, badla nahi ja sakta)</p>
          <ul className="wrap-break-word text-xs text-foreground/60 leading-relaxed list-disc pl-4">
            {barLines(v).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p data-testid={asInfo ? `vehicle-detail-progress-${v.vehicle}` : `vehicle-progress-${v.vehicle}`} className="wrap-break-word text-xs text-foreground/70 mt-1">
            {paperProgress(v)}
          </p>
        </div>
      ) : null}
    </Tag>
  );
}

export function VehiclePicker({ lots, onVehicle, onMoneyness, className, source, compact = false }: Props) {
  const live = (source ?? vehiclePickerSource()) === "live";
  const board = useApi<VehicleBoard>(live ? "/customer-lane/vehicles/board" : null);
  const [vehicle, setVehicle] = useState<CustomerVehicle>("FUTURES");
  const [moneyness, setMoneyness] = useState<Moneyness>(DEFAULT_MONEYNESS);
  const capital = useApi<CapitalLine>(live ? `/customer-lane/vehicles/capital?vehicle=${vehicle}&lots=${lots}` : null);
  const boardData: VehicleBoard | null | undefined = live ? board.data : staticVehicleBoard();
  const takesMoneyness = boardData?.vehicles.find((v) => v.vehicle === vehicle)?.takes_moneyness ?? false;
  const liveTable = useApi<MoneynessTable>(
    live && takesMoneyness && boardData?.strike_selector_enabled ? `/customer-lane/vehicles/moneyness?vehicle=${vehicle}` : null,
  );
  // STATIC mode (C2): the generated snapshot of the same backend table — no server call.
  const table = live ? liveTable : { data: takesMoneyness ? staticMoneynessTable(vehicle) : null };

  // three states, explicitly (the static board has no loading or error of its own)
  if (live && board.isLoading) {
    return <p data-testid="vehicle-picker-loading" className="text-xs text-muted-foreground">Vehicles load ho rahe hain…</p>;
  }
  if (live && board.error) {
    return (
      <p data-testid="vehicle-picker-error" className="text-xs text-loss">
        Vehicles abhi load nahi hue. Page refresh karo; phir bhi na aaye to Madad me likho.
      </p>
    );
  }
  const visible = (boardData?.vehicles ?? []).filter((v) => v.visible);
  if (visible.length === 0) {
    return <p data-testid="vehicle-picker-empty" className="text-xs text-muted-foreground">Abhi koi vehicle offer nahi hai.</p>;
  }
  const cards = groupIntoCards(visible);
  const choose = (v: VehicleStatus) => {
    setVehicle(v.vehicle);
    onVehicle?.(v.vehicle);
  };

  if (compact) {
    // Founder, 26 Sep (settings point 1): one line per vehicle; every other honest
    // word stays, collapsed behind "Aur jaano" (a native disclosure — keyboard and
    // screen-reader operable, closed by default).
    const ordered = cards.flatMap((c) => c.members);
    const segments = [...new Set(ordered.map((v) => VEHICLE_SEGMENT[v.vehicle]))];
    return (
      <div data-testid="vehicle-picker" data-compact="true" data-source={live ? "live" : "static"} className={cn("min-w-0 space-y-2", className)}>
        <div role="radiogroup" aria-label="Kis cheez me chalana hai" className="space-y-2">
          {ordered.map((v) => (
            <VehicleLine key={v.vehicle} v={v} selected={vehicle === v.vehicle} onSelect={() => choose(v)} />
          ))}
        </div>
        <details data-testid="vehicle-more" className="group min-w-0 rounded-lg border border-white/[0.06] px-3">
          <summary className="min-h-tap cursor-pointer py-2.5 text-sm font-medium text-foreground/90">
            Aur jaano
          </summary>
          <div className="min-w-0 space-y-2 pb-3">
            {!live ? (
              <p data-testid="vehicle-picker-static-note" className="wrap-break-word text-xs text-foreground/60 leading-relaxed">
                Abhi sirf dekhne ke liye: chaaron me se koi bhi order nahi bhejta. Har ek ka taala usi bar se khulega jo
                neeche likha hai.
              </p>
            ) : null}
            {ordered.map((v) => {
              const cmp = !live && v.takes_moneyness ? staticMoneynessTable(v.vehicle) : null;
              return (
                <div key={v.vehicle} className="min-w-0 space-y-1.5">
                  <VehicleCard v={v} selected={false} onSelect={() => undefined} asInfo />
                  {cmp ? <MoneynessPicker table={cmp} value={DEFAULT_MONEYNESS} onChange={() => undefined} readOnly /> : null}
                </div>
              );
            })}
            {segments.map((seg) => (
              <p key={seg} data-testid={`worst-day-basis-${seg}`} className="wrap-break-word text-xs text-foreground/60 leading-relaxed">
                {SEGMENT_WORST_DAY[seg].basis}
              </p>
            ))}
            <RiskLegend activeSegment={VEHICLE_SEGMENT[vehicle]} />
            {live && capital.data ? <CapitalLineCard line={capital.data} /> : null}
          </div>
        </details>
        {takesMoneyness && table.data ? (
          <MoneynessPicker
            table={table.data}
            value={moneyness}
            onChange={(m) => {
              setMoneyness(m);
              onMoneyness?.(m);
            }}
          />
        ) : null}
      </div>
    );
  }

  const card = (v: VehicleStatus) => (
    <VehicleCard
      key={v.vehicle}
      v={v}
      selected={vehicle === v.vehicle}
      onSelect={() => choose(v)}
    />
  );

  return (
    <div data-testid="vehicle-picker" data-source={live ? "live" : "static"} className={cn("space-y-3", className)}>
      <div className="text-xs font-medium text-foreground/90">Kis cheez me chalana hai</div>
      {!live ? (
        <p data-testid="vehicle-picker-static-note" className="text-xs text-foreground/60 leading-relaxed">
          Abhi sirf dekhne ke liye: chaaron me se koi bhi order nahi bhejta. Har ek ka taala usi bar se khulega jo
          neeche likha hai.
        </p>
      ) : null}
      <div role="radiogroup" aria-label="Vehicle" className="space-y-2">
        {cards.map((c) =>
          c.members.length === 1 ? (
            card(c.members[0])
          ) : (
            <section key={c.card} data-testid={`vehicle-group-${c.card}`} className="space-y-1.5">
              <div className="text-xs font-medium text-foreground/80">{c.label}</div>
              {c.members.map(card)}
            </section>
          ),
        )}
      </div>

      {!live ? null : capital.isLoading ? (
        <p data-testid="capital-loading" className="text-xs text-muted-foreground">Capital line load ho rahi hai…</p>
      ) : capital.error ? (
        <p data-testid="capital-error" className="text-xs text-loss">Kitna paisa chahiye, yeh abhi load nahi hua — page upar kheench ke refresh karo. Tab tak koi number maan ke mat chalo.</p>
      ) : capital.data ? (
        <CapitalLineCard line={capital.data} />
      ) : null}

      {takesMoneyness && table.data ? (
        <MoneynessPicker
          table={table.data}
          value={moneyness}
          onChange={(m) => {
            setMoneyness(m);
            onMoneyness?.(m);
          }}
        />
      ) : null}

      <p className="text-xs text-foreground/80">
        Agla kadam: kitne lot (packet) chahiye woh chuno — 2, 4, 6… — aur upar ka &ldquo;kam se kam kitna paisa&rdquo; apne Dhan balance se milao.
      </p>
    </div>
  );
}
