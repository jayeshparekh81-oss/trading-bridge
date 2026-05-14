/**
 * SymbolSelector — uncontrolled-looking input with quick-pick chips.
 *
 * Day-5 scope is minimal: a text input that the user types into, plus
 * two quick-pick buttons for the launch defaults (NIFTY, BANKNIFTY).
 * Symbol autocomplete + market hours indicators are explicitly out of
 * scope (those land in Day 4 polish / Day 2 mobile work).
 *
 * The component is controlled via ``value`` + ``onChange`` so the
 * page-level orchestrator owns the source of truth.
 */

"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const QUICK_PICKS: readonly string[] = ["NIFTY", "BANKNIFTY"] as const;

export interface SymbolSelectorProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function SymbolSelector({
  value,
  onChange,
  className,
}: SymbolSelectorProps) {
  return (
    <div
      className={cn("flex items-center gap-2", className)}
      data-testid="symbol-selector"
    >
      <Input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onBlur={(e) => onChange(e.target.value.trim().toUpperCase())}
        placeholder="Symbol (e.g. NIFTY)"
        className="w-40 uppercase"
        aria-label="Trading symbol"
        data-testid="symbol-input"
      />
      <div
        className="hidden gap-1 sm:flex"
        data-testid="symbol-quick-picks"
      >
        {QUICK_PICKS.map((sym) => (
          <Button
            key={sym}
            type="button"
            variant={value === sym ? "default" : "outline"}
            size="sm"
            onClick={() => onChange(sym)}
            data-testid={`symbol-quick-${sym}`}
          >
            {sym}
          </Button>
        ))}
      </div>
    </div>
  );
}
