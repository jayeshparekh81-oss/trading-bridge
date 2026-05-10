"use client";

import { useState } from "react";
import {
  FileJson,
  Wand2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";
import { applyJsonToState, type ExpertState } from "./builder-types";

interface JsonSectionProps {
  payload: unknown;
  catalogue: ReadonlyArray<IndicatorMetadata>;
  onApply: (next: ExpertState) => void;
}

/**
 * Raw JSON editor. The textarea is decoupled from the live ``payload``
 * so the user can edit freely without their cursor jumping when the
 * builder re-renders. ``Sync from builder`` resets the textarea to the
 * current state; ``Apply JSON`` parses + validates the textarea and
 * overwrites builder state on success.
 */
export function JsonSection({ payload, catalogue, onApply }: JsonSectionProps) {
  // Lazy initial value seeds the textarea with the live payload on first
  // mount only — after that the textarea is the source of truth, so we
  // don't sync the prop change back unless the user explicitly clicks
  // ``Sync from builder``. (No useEffect needed.)
  const [text, setText] = useState<string>(() => formatJson(payload));
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  function validate(raw: string) {
    if (raw.trim() === "") {
      setError("JSON empty hai.");
      return;
    }
    try {
      JSON.parse(raw);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Parse error.";
      setError(`Parse error: ${msg}`);
      return;
    }
    setError(null);
  }

  function handleSyncFromBuilder() {
    setText(formatJson(payload));
    setError(null);
    setHint("Builder state se JSON tab refresh ho gaya.");
    setTimeout(() => setHint(null), 2500);
  }

  function handleApply() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Parse error.";
      setError(`Parse error: ${msg}`);
      return;
    }
    const result = applyJsonToState(parsed, catalogue);
    if (result.error || !result.state) {
      setError(result.error ?? "Apply failed.");
      return;
    }
    setError(null);
    onApply(result.state);
    setHint("Builder state JSON se overwrite ho gaya.");
    setTimeout(() => setHint(null), 2500);
  }

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <FileJson className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Raw JSON</h2>
          <span className="ml-auto text-[11px] text-muted-foreground">
            Power-user mode — schema is validated on submit.
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          ``Sync from builder`` se JSON ko current state se refresh karo.
          Edit karne ke baad ``Apply JSON`` se builder state overwrite
          karo. Submit pe Pydantic full validation karega.
        </p>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => validate(text)}
          spellCheck={false}
          className={cn(
            "w-full rounded-md p-3 text-[12px]",
            "bg-black/40 border text-foreground/90",
            error
              ? "border-loss/40 focus:border-loss/60"
              : "border-white/[0.04] focus:border-accent-blue/50",
            "font-mono leading-snug",
            "focus:outline-none focus:ring-2 focus:ring-accent-blue/15",
            "min-h-[18rem] max-h-[40rem]",
          )}
        />

        {error ? (
          <div className="flex items-start gap-2 rounded-md bg-loss/[0.08] border border-loss/30 px-3 py-2">
            <AlertTriangle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
            <p className="text-[11px] text-loss leading-relaxed">{error}</p>
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-md bg-profit/[0.06] border border-profit/30 px-3 py-2">
            <CheckCircle2 className="h-4 w-4 text-profit shrink-0 mt-0.5" />
            <p className="text-[11px] text-profit leading-relaxed">
              JSON parses cleanly. Submit pe schema-level validation
              backend pe hogi.
            </p>
          </div>
        )}

        <div className="flex items-center justify-between gap-2 flex-wrap">
          {hint ? (
            <span className="text-[11px] text-accent-blue">{hint}</span>
          ) : (
            <span className="text-[11px] text-muted-foreground">
              On blur: parses and runs the lossy schema parser.
            </span>
          )}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={handleSyncFromBuilder}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Sync from builder
            </Button>
            <Button
              variant="default"
              size="sm"
              type="button"
              onClick={handleApply}
              disabled={!!error}
            >
              <Wand2 className="h-3.5 w-3.5 mr-1" />
              Apply JSON
            </Button>
          </div>
        </div>
      </div>
    </GlassmorphismCard>
  );
}


function formatJson(payload: unknown): string {
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return "{}";
  }
}
