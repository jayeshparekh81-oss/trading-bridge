/**
 * FAQSearch — debounced search input. Calls onChange after the user
 * stops typing for `debounceMs` (default 200ms) so the filtered FAQ
 * list doesn't re-render on every keystroke.
 *
 * Subtle glow on focus matches the dashboard's other input fields.
 */

"use client";

import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface FAQSearchProps {
  /** Fired after debounce settles. Always called with the trimmed value. */
  onChange: (query: string) => void;
  /** Placeholder text — pass lang-specific copy from the parent. */
  placeholder?: string;
  /** Debounce window in ms. Tests pass 0 to disable the delay. */
  debounceMs?: number;
}

export function FAQSearch({
  onChange,
  placeholder = "Search FAQs...",
  debounceMs = 200,
}: FAQSearchProps) {
  const [value, setValue] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }
    if (debounceMs <= 0) {
      onChange(value.trim());
      return;
    }
    timerRef.current = setTimeout(() => {
      onChange(value.trim());
    }, debounceMs);
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, [value, debounceMs, onChange]);

  return (
    <div
      data-testid="help-search"
      className="relative w-full"
    >
      <Search
        className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        data-testid="help-search-input"
        className="w-full h-10 pl-9 pr-3 rounded-lg border border-white/10 bg-neutral-900/60 text-sm text-neutral-100 placeholder:text-neutral-500 outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 transition-colors"
      />
    </div>
  );
}
