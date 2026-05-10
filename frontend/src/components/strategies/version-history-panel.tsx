"use client";

/**
 * Version history panel for the strategy detail page.
 *
 * Shows the full edit history of a strategy as a vertical timeline,
 * newest first, with a "Current" badge on the latest version. Clicking
 * a row opens the diff modal comparing that version to current; the
 * rollback button on non-current rows confirms then writes a new
 * version mirroring the target's payload (POST .../rollback).
 *
 * Backend contract:
 *   GET  /api/strategies/{id}/versions            list[StrategyVersion]
 *   POST /api/strategies/{id}/versions/{n}/rollback → StrategyResponse
 *
 * Loaded lazily via the parent's <details>/expandable wrapper — the
 * panel itself doesn't gate the fetch, so once mounted it always
 * fires the GET. No auto-refresh: history only changes on user
 * action (edit, rollback) and the parent page re-fetches via
 * ``onChanged`` after a rollback.
 */

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import {
  History,
  RotateCcw,
  GitCommitHorizontal,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlowButton } from "@/components/ui/glow-button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useApi } from "@/lib/use-api";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { VersionDiffModal } from "@/components/strategies/version-diff-modal";

export interface StrategyVersion {
  version_id: string;
  strategy_id: string;
  version_number: number;
  strategy_json: Record<string, unknown>;
  change_summary: string;
  created_by: string;
  created_at: string;
  parent_version_id: string | null;
}

interface VersionHistoryPanelProps {
  strategyId: string;
  /**
   * Called after a successful rollback so the parent page can re-fetch
   * the strategy row (the live ``strategy_json`` was just rewritten).
   */
  onChanged?: () => void;
}

export function VersionHistoryPanel({
  strategyId,
  onChanged,
}: VersionHistoryPanelProps) {
  const { data, isLoading, error, refetch } = useApi<StrategyVersion[]>(
    `/strategies/${strategyId}/versions`,
    [],
  );

  const [diffTarget, setDiffTarget] = useState<StrategyVersion | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<StrategyVersion | null>(
    null,
  );
  const [isRollingBack, setIsRollingBack] = useState(false);

  const versions = (data ?? []).slice().reverse(); // newest first
  const current = versions[0] ?? null;

  const confirmRollback = useCallback(async () => {
    if (!rollbackTarget) return;
    setIsRollingBack(true);
    try {
      await api.post(
        `/strategies/${strategyId}/versions/${rollbackTarget.version_number}/rollback`,
      );
      toast.success(
        `🎉🎉 Version restore ho gaya — v${rollbackTarget.version_number} ki content ab live hai.`,
      );
      setRollbackTarget(null);
      refetch();
      onChanged?.();
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.detail : "Rollback fail ho gaya";
      toast.error(detail);
    } finally {
      setIsRollingBack(false);
    }
  }, [rollbackTarget, strategyId, refetch, onChanged]);

  return (
    <>
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-base" aria-hidden>
                📜
              </span>
              <h3 className="font-semibold text-sm flex items-center gap-1.5">
                <History className="h-3.5 w-3.5 text-accent-blue" />
                Version History
              </h3>
              {versions.length > 0 ? (
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 h-5"
                >
                  {versions.length}
                </Badge>
              ) : null}
            </div>
            {error ? (
              <Button variant="ghost" size="sm" onClick={refetch} type="button">
                Retry
              </Button>
            ) : null}
          </div>

          {error && versions.length === 0 ? (
            <ErrorState message={error} />
          ) : isLoading && versions.length === 0 ? (
            <LoadingState />
          ) : versions.length === 0 ? (
            <EmptyState />
          ) : (
            <ol className="space-y-2">
              {versions.map((v, idx) => {
                const isCurrent = idx === 0;
                return (
                  <VersionRow
                    key={v.version_id}
                    version={v}
                    isCurrent={isCurrent}
                    onShowDiff={() => setDiffTarget(v)}
                    onRequestRollback={() => setRollbackTarget(v)}
                  />
                );
              })}
            </ol>
          )}
        </div>
      </GlassmorphismCard>

      <Dialog
        open={!!rollbackTarget}
        onOpenChange={(open) => {
          if (!open && !isRollingBack) setRollbackTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-amber-500" />
              Rollback confirm karein?
            </DialogTitle>
            <DialogDescription>
              {rollbackTarget && current ? (
                <span>
                  Yeh version restore karoge? Current version v
                  {current.version_number} preserve rahega history mein —
                  rollback ek naya version (v{current.version_number + 1})
                  banayega jo v{rollbackTarget.version_number} ki content
                  copy karega.
                </span>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setRollbackTarget(null)}
              disabled={isRollingBack}
              type="button"
            >
              Cancel
            </Button>
            <GlowButton
              onClick={confirmRollback}
              disabled={isRollingBack}
              type="button"
            >
              {isRollingBack ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Rolling back…
                </>
              ) : (
                <>
                  <RotateCcw className="h-3.5 w-3.5" />
                  Rollback to v{rollbackTarget?.version_number}
                </>
              )}
            </GlowButton>
          </div>
        </DialogContent>
      </Dialog>

      {diffTarget && current && diffTarget.version_id !== current.version_id ? (
        <VersionDiffModal
          strategyId={strategyId}
          fromVersion={diffTarget.version_number}
          toVersion={current.version_number}
          open={!!diffTarget}
          onOpenChange={(open) => {
            if (!open) setDiffTarget(null);
          }}
        />
      ) : null}
    </>
  );
}

function VersionRow({
  version,
  isCurrent,
  onShowDiff,
  onRequestRollback,
}: {
  version: StrategyVersion;
  isCurrent: boolean;
  onShowDiff: () => void;
  onRequestRollback: () => void;
}) {
  const created = formatDate(version.created_at);
  const summary = version.change_summary || "No change notes";

  return (
    <motion.li
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "rounded-lg border bg-white/[0.02] p-3 transition-colors",
        "hover:bg-white/[0.04]",
        isCurrent
          ? "border-accent-blue/30"
          : "border-white/[0.06] cursor-pointer",
      )}
      onClick={() => {
        if (!isCurrent) onShowDiff();
      }}
      title={isCurrent ? undefined : version.change_summary}
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.06]">
              v{version.version_number}
            </span>
            {isCurrent ? (
              <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
                Current
              </Badge>
            ) : null}
            <span className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
              <GitCommitHorizontal className="h-3 w-3" />
              {created}
            </span>
          </div>
          <p
            className="text-xs text-foreground/85 mt-1 line-clamp-2"
            title={summary}
          >
            {summary}
          </p>
        </div>
        {!isCurrent ? (
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onRequestRollback();
            }}
            type="button"
            className="shrink-0"
          >
            <RotateCcw className="h-3 w-3" />
            Rollback
          </Button>
        ) : null}
      </div>
    </motion.li>
  );
}

function EmptyState() {
  return (
    <div className="text-xs text-muted-foreground text-center py-4">
      Abhi tak koi version record nahi hai. Strategy edit karoge to history
      yahaan dikhegi.
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-12 rounded-lg bg-white/[0.04]" />
      <div className="h-12 rounded-lg bg-white/[0.03]" />
      <div className="h-12 rounded-lg bg-white/[0.02]" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="text-center py-4">
      <AlertTriangle className="h-6 w-6 text-loss mx-auto mb-2" />
      <p className="text-xs text-muted-foreground">{message}</p>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return "—";
  }
}
