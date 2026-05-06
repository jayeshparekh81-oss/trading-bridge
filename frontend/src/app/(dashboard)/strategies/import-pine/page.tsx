"use client";

/**
 * Pine Script Import — frontend entry point for the Phase 7 importer.
 *
 * Two-column layout (single column on mobile):
 *   left  — paste-source textarea + Convert button
 *   right — result panel (idle / loading / success / partial / failure)
 *
 * On success / partial-with-converted, the user can save the converted
 * strategy via ``POST /api/strategies`` (existing endpoint) and is then
 * redirected to ``/strategies/{id}/backtest``. The backtest page
 * auto-runs the backtest in its own ``useEffect``, mirroring the
 * post-builder flow used by the three Phase 5B builders.
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, X, FileCode2 } from "lucide-react";
import { toast } from "sonner";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { api, ApiError } from "@/lib/api";
import { celebrationCopy } from "@/lib/celebration";
import { SourceInput } from "@/components/strategies/pine-importer/source-input";
import { ResultPanel } from "@/components/strategies/pine-importer/result-panel";
import type { PineImportResponse } from "@/components/strategies/pine-importer/types";


type PanelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "result"; response: PineImportResponse };


interface CreatedStrategy {
  id: string;
  name: string;
}


export default function PineImportPage() {
  const router = useRouter();
  const [source, setSource] = useState("");
  const [panel, setPanel] = useState<PanelState>({ kind: "idle" });
  const [saving, setSaving] = useState(false);

  async function handleConvert() {
    setPanel({ kind: "loading" });
    try {
      const result = await api.post<PineImportResponse>(
        "/strategies/pine-import",
        { pine_source: source },
      );
      setPanel({ kind: "result", response: result });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : "Convert ho nahi paya. Network ya backend issue.";
      setPanel({ kind: "error", message });
    }
  }

  /**
   * Save the converted strategy. Called from the success and partial
   * panels — the converter's ``strategy`` and ``converted`` fields
   * carry a StrategyJSON-shaped dict that POST /api/strategies
   * accepts directly via its ``strategy_json`` body wrapper.
   */
  async function handleSave(useConverted: boolean) {
    if (panel.kind !== "result" || !panel.response) return;
    const payload = panel.response.success
      ? panel.response.strategy
      : useConverted
        ? panel.response.converted
        : null;
    if (!payload) {
      toast.error("Kuch save karne ke liye nahi hai.");
      return;
    }

    setSaving(true);
    try {
      const created = await api.post<CreatedStrategy>("/strategies", {
        strategy_json: payload,
      });
      toast.success(celebrationCopy("medium", "Pine strategy saved"));
      router.push(`/strategies/${created.id}/backtest`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Save nahi ho paya. Backend Pydantic validation fail ho gaya hoga.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      {/* Header */}
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to strategies
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileCode2 className="h-6 w-6 text-accent-blue" />
            Pine Script Import{" "}
            <span aria-hidden="true">🚀</span>
          </h1>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Apni TradingView Pine script paste karo. Tradetri convert
            karega — pure-Python parser, no eval / no network. Supported
            subset ke saath schema-validated StrategyJSON niklega.
          </p>
        </div>
        <Link
          href="/strategies"
          className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-white/[0.04] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground transition-colors"
        >
          <X className="h-3 w-3" />
          Cancel
        </Link>
      </header>

      {/* Hint banner */}
      <GlassmorphismCard hover={false}>
        <div className="text-[12px] text-muted-foreground leading-relaxed">
          <strong className="text-foreground">Tip:</strong> Pine v5 / v6
          supported. License headers detected automatically — protected /
          invite-only / paid scripts cannot be imported. ``request.security``
          aur similar runtime calls supported nahi hain.
        </div>
      </GlassmorphismCard>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SourceInput
          source={source}
          onSourceChange={setSource}
          onConvert={handleConvert}
          isLoading={panel.kind === "loading"}
        />
        <ResultPanel
          state={panel}
          onSave={() => handleSave(false)}
          onSavePartial={() => handleSave(true)}
          saving={saving}
        />
      </div>
    </motion.div>
  );
}
