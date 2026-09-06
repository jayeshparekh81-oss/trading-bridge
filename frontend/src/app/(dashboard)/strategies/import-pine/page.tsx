"use client";

/**
 * Pine import — frontend entry point for the Phase 7 importer. The name is
 * the sidebar's ("Pine import"), and the header comes from the template.
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
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { ProPage } from "@/components/dashboard/pro-page";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { api, ApiError } from "@/shared/api/client";
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
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto"
    >
      {/* The header is the template's: title, one line, no primary action —
          Convert lives with the textarea it acts on, in the left column. */}
      <ProPage
        title="Pine import"
        blurb="TradingView ki Pine script paste karo — Tradetri usse strategy mein convert karega."
        action={null}
      >
        {/* Hint banner */}
        <GlassmorphismCard hover={false}>
          <div className="text-xs text-muted-foreground leading-relaxed">
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
      </ProPage>
    </motion.div>
  );
}
