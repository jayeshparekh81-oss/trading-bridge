"use client";

import { useState } from "react";
import { Code2, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface StrategyJsonPreviewProps {
  payload: unknown;
  /** When set, the preview is treated as not-yet-valid and shows a hint. */
  invalidReason: string | null;
}

export function StrategyJsonPreview({
  payload,
  invalidReason,
}: StrategyJsonPreviewProps) {
  const [open, setOpen] = useState(false);
  const text = payload === null ? "null" : JSON.stringify(payload, null, 2);

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full flex items-center gap-2 text-left"
          aria-expanded={open}
        >
          <Code2 className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Strategy JSON</h2>
          <span className="ml-auto text-[11px] text-muted-foreground">
            {open ? "Hide" : "Show"} raw payload
          </span>
          {open ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {invalidReason ? (
          <div className="flex items-start gap-2 rounded-md bg-loss/[0.08] border border-loss/30 px-3 py-2">
            <AlertTriangle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
            <p className="text-[11px] text-loss leading-relaxed">
              {invalidReason}
            </p>
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Payload backend ke ``StrategyJSON`` schema ke hisaab se
            structurally valid hai. Submit pe Pydantic ek aur layer pe
            check karega.
          </p>
        )}

        {open ? (
          <div className="rounded-md bg-black/40 border border-white/[0.04] overflow-hidden">
            <pre
              className={cn(
                "text-[11px] leading-snug p-3 overflow-x-auto",
                "font-mono text-foreground/90",
                "max-h-96 overflow-y-auto",
              )}
            >
              <code>{text}</code>
            </pre>
            <div className="border-t border-white/[0.04] px-3 py-2 flex items-center justify-end">
              <CopyButton text={text} />
            </div>
          </div>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (e.g. http context) — silently no-op; the
      // raw JSON remains visible above so the user can hand-select it.
    }
  }

  return (
    <Button
      variant="ghost"
      size="xs"
      onClick={handleCopy}
      type="button"
    >
      {copied ? "Copied!" : "Copy"}
    </Button>
  );
}
