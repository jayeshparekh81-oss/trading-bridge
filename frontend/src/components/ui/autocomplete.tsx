"use client";

/**
 * Thin shadcn-style wrapper around `@base-ui/react/combobox`.
 *
 * Named ``Autocomplete`` for clarity — Base UI ships both a
 * ``combobox`` and an ``autocomplete`` primitive, but the latter
 * is strict-text-mode only (only accepts primitive-string items
 * and Omits the item-stringify props). For our object items
 * (``{label, value}``) the right primitive is ``combobox`` with
 * Multiple=false; the file/component name preserves the Autocomplete
 * naming from the design discussion to avoid bikeshedding.
 *
 * Used by the strategy candle-source picker (Step 3) to surface 216+
 * F&O indices and stocks with type-to-filter UX. Replaces the native
 * `<datalist>` which became qualitatively broken at this scale,
 * especially on mobile.
 *
 * Free-text fallback is non-negotiable here — the backend's
 * normalise_symbol + SYMBOL_ALIASES path resolves arbitrary user
 * input via canonical-name + alias matching. ``onInputValueChange``
 * fires on every keystroke regardless of whether the typed value
 * matches a list item, preserving the contract.
 *
 * Filter: case-insensitive substring match against both ``label`` and
 * ``value``. Substring (not prefix) so "RELI" matches "Reliance
 * Industries" by label and "RELIANCE" by value.
 */

import * as React from "react";
import { Combobox as ComboboxPrimitive } from "@base-ui/react/combobox";

import { cn } from "@/lib/utils";

export interface AutocompleteItem {
  label: string;
  value: string;
}

interface AutocompleteProps {
  /** Controlled input value (the text in the input). */
  value: string;
  /** Fires on every keystroke AND when an item is selected (after
   *  Base UI stringifies the picked item via ``itemToStringValue``).
   *  The emitted string is the canonical ``item.value`` on selection,
   *  or the raw typed string on free-text input. */
  onValueChange: (value: string) => void;
  /** Item list. Filtering and ARIA wiring handled by Base UI; the
   *  caller provides plain ``{label, value}`` objects. */
  items: ReadonlyArray<AutocompleteItem>;
  placeholder?: string;
  id?: string;
  /** Optional extra classes for the input element. */
  className?: string;
  /** Empty-state copy when no item matches the current query. The
   *  free-text fallback path stays open regardless. */
  emptyMessage?: string;
}

function defaultFilter(item: AutocompleteItem, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    item.label.toLowerCase().includes(q) ||
    item.value.toLowerCase().includes(q)
  );
}

export function Autocomplete({
  value,
  onValueChange,
  items,
  placeholder,
  id,
  className,
  emptyMessage = "No matches — typed value is sent to the backend as-is.",
}: AutocompleteProps) {
  // Bug #1 v2 — Base UI Combobox filter-on-mount workaround.
  // When ``inputValue`` is non-empty on mount (e.g. expert mode seeds
  // it with "NIFTY" via ``defaultCandlesRequest()``), Base UI applies
  // ``filter`` to the items list using ``inputValue`` as the query
  // before the user has typed anything — first click of the picker
  // shows only items whose label/value contain the seeded string.
  // While the user has not typed, pass ``filter={null}`` so Base UI
  // skips filtering and returns the full list. Reset on popup close
  // so re-opening with a pre-filled value (selection, edit-mode
  // hydration) again shows the full list.
  const [hasUserTyped, setHasUserTyped] = React.useState(false);

  return (
    <ComboboxPrimitive.Root
      // Free-text-mode contract: ``inputValue`` is the controlled
      // string, ``onInputValueChange`` fires per keystroke and when
      // an item is selected (Base UI populates the input via
      // ``itemToStringValue``). We ignore the separate ``value`` /
      // ``onValueChange`` item-selection state since we only care
      // about the text the user/picker sees and submits.
      inputValue={value}
      onInputValueChange={(next: string, details: { reason?: string }) => {
        // Only actual typing (reason="inputChange") flips the filter
        // gate. Selection (itemPress), clears, and programmatic value
        // updates emit other reasons and don't trigger filtering.
        if (details?.reason === "inputChange") setHasUserTyped(true);
        onValueChange(next);
      }}
      onOpenChange={(open: boolean) => {
        if (!open) setHasUserTyped(false);
      }}
      items={items as readonly AutocompleteItem[]}
      itemToStringValue={(item: AutocompleteItem) => item.value}
      itemToStringLabel={(item: AutocompleteItem) => item.label}
      isItemEqualToValue={(a: AutocompleteItem, b: AutocompleteItem) =>
        a.value === b.value
      }
      // While the user hasn't typed, skip filtering (Base UI:
      // ``filter=null`` returns all items). Once they type, apply the
      // substring filter.
      filter={hasUserTyped ? defaultFilter : null}
    >
      <ComboboxPrimitive.Input
        id={id}
        placeholder={placeholder}
        className={cn(
          "w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs",
          "outline-none focus-visible:ring-1 focus-visible:ring-accent-blue/40",
          className,
        )}
      />
      <ComboboxPrimitive.Portal>
        <ComboboxPrimitive.Positioner
          sideOffset={4}
          align="start"
          className="isolate z-50"
        >
          <ComboboxPrimitive.Popup
            data-slot="autocomplete-popup"
            className={cn(
              "max-h-[260px] w-(--anchor-width) min-w-[180px] overflow-y-auto",
              "rounded-md bg-popover text-popover-foreground shadow-md",
              "ring-1 ring-foreground/10 p-1",
              "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
              "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            )}
          >
            <ComboboxPrimitive.List>
              {(item: AutocompleteItem) => (
                <ComboboxPrimitive.Item
                  key={item.value}
                  value={item}
                  className={cn(
                    "flex items-baseline gap-2 rounded-sm px-2 py-1.5",
                    "text-xs cursor-default select-none outline-none",
                    "data-[highlighted]:bg-accent-blue/15",
                    "data-[highlighted]:text-accent-blue",
                  )}
                >
                  <span className="font-medium truncate">{item.label}</span>
                  {item.label !== item.value ? (
                    <span className="ml-auto text-[10px] font-mono text-muted-foreground/70">
                      {item.value}
                    </span>
                  ) : null}
                </ComboboxPrimitive.Item>
              )}
            </ComboboxPrimitive.List>
            <ComboboxPrimitive.Empty
              className="px-2 py-1.5 text-[11px] text-muted-foreground"
            >
              {emptyMessage}
            </ComboboxPrimitive.Empty>
          </ComboboxPrimitive.Popup>
        </ComboboxPrimitive.Positioner>
      </ComboboxPrimitive.Portal>
    </ComboboxPrimitive.Root>
  );
}
