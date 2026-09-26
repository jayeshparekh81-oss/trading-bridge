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
import { NOT_MEASURED } from "@/lib/risk-labels";
import {
  DIRECTION_CHOICES,
  FUTURES_LOT_CHOICES,
  barLines,
  groupIntoCards,
  paperProgress,
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
}

const rupees = (n: number) => formatCurrency(n, { compact: true });

function Figure({ label, value, basis, testId }: { label: string; value: number | string; basis: string; testId: string }) {
  const measured = typeof value === "number";
  return (
    <div data-testid={testId} data-measured={measured ? "true" : "false"} className="py-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-11 text-muted-foreground">{label}</span>
        <span className={cn("text-12 font-medium", measured ? "text-foreground" : "text-amber-300")}>
          {measured ? rupees(value) : NOT_MEASURED}
        </span>
      </div>
      {/* the basis is VISIBLE copy, never tooltip-only */}
      <p data-testid={`${testId}-basis`} className="text-10 text-foreground/50 leading-relaxed">
        {basis}
      </p>
    </div>
  );
}

export function CapitalLineCard({ line }: { line: CapitalLine }) {
  return (
    <section data-testid="capital-line" className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="text-11 font-medium text-foreground/90">
        Kitna paisa chahiye — {line.lots} lots
        {typeof line.lot_size === "number" ? ` (${line.lots * line.lot_size} shares)` : ""}
      </div>
      <Figure label="Minimum capital" value={line.minimum_capital.value} basis={line.minimum_capital.basis} testId="capital-minimum" />
      <Figure label="Margin (NRML)" value={line.margin.value} basis={line.margin.basis} testId="capital-margin" />
      <Figure label="Worst drawdown" value={line.max_drawdown.value} basis={line.max_drawdown.basis} testId="capital-drawdown" />
      <Figure label="Worst day" value={line.worst_day.value} basis={line.worst_day.basis} testId="capital-worst-day" />
      <p className="text-10 text-muted-foreground leading-relaxed mt-1">
        Rule: <span className="font-mono">{line.rule}</span>. {line.rule_text}
      </p>
      {line.margin_stale ? (
        <p data-testid="capital-margin-stale" className="text-10 text-amber-300/80 leading-relaxed mt-1">
          Margin ka number {line.margin.as_of ?? "?"} ka hai — 7 din se purana. Broker par aaj ka margin alag ho sakta hai.
        </p>
      ) : null}
    </section>
  );
}

export function MoneynessPicker({
  table,
  value,
  onChange,
}: {
  table: MoneynessTable;
  value: Moneyness;
  onChange: (m: Moneyness) => void;
}) {
  const rows = defaultFirst(table.rows);
  return (
    <section data-testid="moneyness-picker" className="space-y-2">
      <div className="text-11 font-medium text-foreground/90">Strike kaunsa — aapki choice</div>
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
              <span className="block text-9 uppercase tracking-wide text-profit">Recommended (default)</span>
            ) : null}
          </button>
        ))}
      </div>
      <p data-testid="moneyness-default-basis" className="text-10 text-foreground/50 leading-relaxed">
        Default OTM: {table.default_basis}
      </p>
      {/* the comparison table: net · drawdown · win rate · trades · period, every row */}
      <ul className="space-y-1.5">
        {rows.map((r) => (
          <li
            key={r.moneyness}
            data-testid={`moneyness-row-${r.moneyness}`}
            data-measured={r.measured ? "true" : "false"}
            className="rounded-md border border-white/[0.06] bg-white/[0.02] p-2 text-10"
          >
            <div className="flex justify-between">
              <span className="font-medium text-foreground/90">{r.moneyness}</span>
              <span className="text-muted-foreground">{r.trades} trades · {r.period}</span>
            </div>
            <div className="grid grid-cols-3 gap-1 mt-1">
              <span>Net: {cell(r.net_after_charges_rupees, rupees)}</span>
              <span>Drawdown: {cell(r.worst_drawdown_rupees, rupees)}</span>
              <span>Win rate: {winRateBesideDrawdown(r)}</span>
            </div>
            <p className="text-foreground/50 leading-relaxed mt-1">{r.source}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function VehicleCard({ v, selected, onSelect }: { v: VehicleStatus; selected: boolean; onSelect: () => void }) {
  const plain = VEHICLE_PLAIN[v.vehicle];
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      data-testid={`vehicle-card-${v.vehicle}`}
      data-open={v.open ? "true" : "false"}
      onClick={onSelect}
      className={cn(
        "w-full text-left rounded-lg border p-3 min-h-14",
        selected ? "border-profit/60 bg-profit/10" : "border-white/[0.08] bg-white/[0.02]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-12 font-medium text-foreground">{plain.label}</span>
        {v.open ? (
          <span className="text-9 uppercase tracking-wide text-profit">Khula hai</span>
        ) : (
          <span className="text-9 uppercase tracking-wide text-amber-300 flex items-center gap-1">
            <Lock className="h-3 w-3" aria-hidden /> Band
          </span>
        )}
      </div>
      <p className="text-10 text-muted-foreground leading-relaxed mt-1">{plain.what}</p>
      {v.has_live_record ? (
        <p className="text-10 text-foreground/60 mt-1">Asli live record hai (20 Aug 2026 se).</p>
      ) : null}
      {!v.open ? (
        <p data-testid={`vehicle-waiting-${v.vehicle}`} className="text-10 text-amber-300/80 leading-relaxed mt-1">
          {lockLine(v)}
        </p>
      ) : null}
      {v.vehicle === "FUTURES" ? (
        <p data-testid="vehicle-futures-choices" className="text-10 text-foreground/60 leading-relaxed mt-1">
          Lots: {FUTURES_LOT_CHOICES.join(" · ")} · Direction: {DIRECTION_CHOICES.map((d) => d.label).join(" / ")}
        </p>
      ) : null}
      {!v.open && v.vehicle !== "FUTURES" && barLines(v).length ? (
        <div data-testid={`vehicle-bar-${v.vehicle}`} className="mt-1.5 rounded-md border border-white/[0.06] p-2">
          <p className="text-10 font-medium text-foreground/80">Iska evidence bar (24 Sep ko seal hua, badla nahi ja sakta)</p>
          <ul className="text-10 text-foreground/60 leading-relaxed list-disc pl-4">
            {barLines(v).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p data-testid={`vehicle-progress-${v.vehicle}`} className="text-10 text-foreground/70 mt-1">
            {paperProgress(v)}
          </p>
        </div>
      ) : null}
    </button>
  );
}

export function VehiclePicker({ lots, onVehicle, onMoneyness, className, source }: Props) {
  const live = (source ?? vehiclePickerSource()) === "live";
  const board = useApi<VehicleBoard>(live ? "/customer-lane/vehicles/board" : null);
  const [vehicle, setVehicle] = useState<CustomerVehicle>("FUTURES");
  const [moneyness, setMoneyness] = useState<Moneyness>(DEFAULT_MONEYNESS);
  const capital = useApi<CapitalLine>(live ? `/customer-lane/vehicles/capital?vehicle=${vehicle}&lots=${lots}` : null);
  const boardData: VehicleBoard | null | undefined = live ? board.data : staticVehicleBoard();
  const takesMoneyness = boardData?.vehicles.find((v) => v.vehicle === vehicle)?.takes_moneyness ?? false;
  const table = useApi<MoneynessTable>(
    live && takesMoneyness && boardData?.strike_selector_enabled ? `/customer-lane/vehicles/moneyness?vehicle=${vehicle}` : null,
  );

  // three states, explicitly (the static board has no loading or error of its own)
  if (live && board.isLoading) {
    return <p data-testid="vehicle-picker-loading" className="text-11 text-muted-foreground">Vehicles load ho rahe hain…</p>;
  }
  if (live && board.error) {
    return (
      <p data-testid="vehicle-picker-error" className="text-11 text-loss">
        Vehicles abhi load nahi hue. Page refresh karo; phir bhi na aaye to Madad me likho.
      </p>
    );
  }
  const visible = (boardData?.vehicles ?? []).filter((v) => v.visible);
  if (visible.length === 0) {
    return <p data-testid="vehicle-picker-empty" className="text-11 text-muted-foreground">Abhi koi vehicle offer nahi hai.</p>;
  }
  const cards = groupIntoCards(visible);
  const card = (v: VehicleStatus) => (
    <VehicleCard
      key={v.vehicle}
      v={v}
      selected={vehicle === v.vehicle}
      onSelect={() => {
        setVehicle(v.vehicle);
        onVehicle?.(v.vehicle);
      }}
    />
  );

  return (
    <div data-testid="vehicle-picker" data-source={live ? "live" : "static"} className={cn("space-y-3", className)}>
      <div className="text-11 font-medium text-foreground/90">Kis cheez me chalana hai</div>
      {!live ? (
        <p data-testid="vehicle-picker-static-note" className="text-10 text-foreground/60 leading-relaxed">
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
              <div className="text-11 font-medium text-foreground/80">{c.label}</div>
              {c.members.map(card)}
            </section>
          ),
        )}
      </div>

      {!live ? null : capital.isLoading ? (
        <p data-testid="capital-loading" className="text-11 text-muted-foreground">Capital line load ho rahi hai…</p>
      ) : capital.error ? (
        <p data-testid="capital-error" className="text-11 text-loss">Capital line abhi nahi aayi. Refresh karo.</p>
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

      <p className="text-11 text-foreground/80">
        Agla step: lots chuno (even number) aur upar ka minimum capital apne Dhan balance se milao.
      </p>
    </div>
  );
}
