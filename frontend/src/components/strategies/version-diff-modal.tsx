"use client";

/**
 * Side-by-side diff modal — used by the version history panel when
 * the user clicks a non-current version row.
 *
 * Calls ``GET /api/strategies/{id}/versions/compare?from_version=X&to_version=Y``
 * and renders the :class:`StrategyVersionComparison` payload grouped by
 * top-level section (Indicators / Entry / Exit / Risk / Other) with
 * colour-coded change types: green added, red removed, amber modified.
 *
 * The Hinglish summary from the backend is shown verbatim at the top
 * — the model already produces beginner-friendly wording so we don't
 * re-massage it on the client.
 */

import { useMemo } from "react";
import {
  GitBranch,
  Plus,
  Minus,
  Pencil,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type ChangeType = "added" | "modified" | "removed";

interface StrategyVersionDiff {
  field_path: string;
  old_value: unknown;
  new_value: unknown;
  change_type: ChangeType;
}

interface StrategyVersionComparison {
  from_version: number;
  to_version: number;
  diffs: StrategyVersionDiff[];
  summary_hinglish: string;
}

interface VersionDiffModalProps {
  strategyId: string;
  fromVersion: number;
  toVersion: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SECTION_PREFIXES: Array<{ key: string; label: string; matches: (path: string) => boolean }> = [
  {
    key: "indicators",
    label: "Indicators",
    matches: (p) => p === "indicators" || p.startsWith("indicators[") || p.startsWith("indicators."),
  },
  {
    key: "entry",
    label: "Entry",
    matches: (p) => p === "entry" || p.startsWith("entry.") || p.startsWith("entry["),
  },
  {
    key: "exit",
    label: "Exit",
    matches: (p) => p === "exit" || p.startsWith("exit.") || p.startsWith("exit["),
  },
  {
    key: "risk",
    label: "Risk",
    matches: (p) => p === "risk" || p.startsWith("risk.") || p.startsWith("risk["),
  },
];

export function VersionDiffModal({
  strategyId,
  fromVersion,
  toVersion,
  open,
  onOpenChange,
}: VersionDiffModalProps) {
  // ``useApi`` already encapsulates the loading/error/cancel pattern.
  // Passing ``null`` while the modal is closed skips the fetch.
  const { data, isLoading, error } = useApi<StrategyVersionComparison>(
    open
      ? `/strategies/${strategyId}/versions/compare?from_version=${fromVersion}&to_version=${toVersion}`
      : null,
  );

  const grouped = useMemo(() => groupBySection(data?.diffs ?? []), [data]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-accent-blue" />
            Compare v{fromVersion} → v{toVersion}
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-10 text-muted-foreground text-xs gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Diff calculate ho raha hai…
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <AlertTriangle className="h-7 w-7 text-loss mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
        ) : data ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 px-3 py-2 text-xs leading-relaxed">
              {data.summary_hinglish}
            </div>

            {data.diffs.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-4">
                Koi changes nahi — dono versions identical hain.
              </div>
            ) : (
              <div className="space-y-4">
                {SECTION_PREFIXES.map(({ key, label }) => {
                  const items = grouped[key] ?? [];
                  if (items.length === 0) return null;
                  return (
                    <DiffSection key={key} label={label} diffs={items} />
                  );
                })}
                {grouped["__other__"]?.length ? (
                  <DiffSection label="Other" diffs={grouped["__other__"]} />
                ) : null}
              </div>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function DiffSection({
  label,
  diffs,
}: {
  label: string;
  diffs: StrategyVersionDiff[];
}) {
  const counts = countByType(diffs);
  return (
    <section className="rounded-lg border border-white/[0.05] bg-white/[0.015]">
      <header className="flex items-center justify-between px-3 py-2 border-b border-white/[0.04]">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </h4>
        <div className="flex items-center gap-1.5">
          {counts.added > 0 ? (
            <Badge className="bg-profit/15 text-profit border-profit/30 text-[10px]">
              +{counts.added}
            </Badge>
          ) : null}
          {counts.removed > 0 ? (
            <Badge className="bg-loss/15 text-loss border-loss/30 text-[10px]">
              −{counts.removed}
            </Badge>
          ) : null}
          {counts.modified > 0 ? (
            <Badge className="bg-amber-500/15 text-amber-500 border-amber-500/30 text-[10px]">
              ~{counts.modified}
            </Badge>
          ) : null}
        </div>
      </header>
      <ul className="divide-y divide-white/[0.04]">
        {diffs.map((d, idx) => (
          <DiffRow key={`${d.field_path}-${idx}`} diff={d} />
        ))}
      </ul>
    </section>
  );
}

function DiffRow({ diff }: { diff: StrategyVersionDiff }) {
  const tone = toneFor(diff.change_type);
  return (
    <li className="px-3 py-2 text-xs">
      <div className="flex items-center gap-2 mb-1">
        <span className={cn("inline-flex items-center gap-1", tone.text)}>
          {diff.change_type === "added" ? (
            <Plus className="h-3 w-3" />
          ) : diff.change_type === "removed" ? (
            <Minus className="h-3 w-3" />
          ) : (
            <Pencil className="h-3 w-3" />
          )}
          <span className="uppercase tracking-wide font-semibold text-[10px]">
            {diff.change_type}
          </span>
        </span>
        <code className="text-[11px] text-muted-foreground font-mono">
          {diff.field_path}
        </code>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <ValueCell
          label="old"
          value={diff.old_value}
          empty={diff.change_type === "added"}
          tone={diff.change_type === "removed" ? "loss" : "muted"}
        />
        <ValueCell
          label="new"
          value={diff.new_value}
          empty={diff.change_type === "removed"}
          tone={diff.change_type === "added" ? "profit" : "muted"}
        />
      </div>
    </li>
  );
}

function ValueCell({
  label,
  value,
  empty,
  tone,
}: {
  label: string;
  value: unknown;
  empty: boolean;
  tone: "profit" | "loss" | "muted";
}) {
  const toneClass =
    tone === "profit"
      ? "border-profit/20 bg-profit/5"
      : tone === "loss"
        ? "border-loss/20 bg-loss/5"
        : "border-white/[0.05] bg-white/[0.02]";
  return (
    <div className={cn("rounded-md border px-2 py-1.5", toneClass)}>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
        {label}
      </div>
      <div className="font-mono text-[11px] break-all whitespace-pre-wrap">
        {empty ? <span className="text-muted-foreground italic">—</span> : formatValue(value)}
      </div>
    </div>
  );
}

function toneFor(change: ChangeType): { text: string } {
  switch (change) {
    case "added":
      return { text: "text-profit" };
    case "removed":
      return { text: "text-loss" };
    case "modified":
      return { text: "text-amber-500" };
  }
}

function countByType(diffs: StrategyVersionDiff[]) {
  let added = 0;
  let removed = 0;
  let modified = 0;
  for (const d of diffs) {
    if (d.change_type === "added") added += 1;
    else if (d.change_type === "removed") removed += 1;
    else modified += 1;
  }
  return { added, removed, modified };
}

function groupBySection(
  diffs: StrategyVersionDiff[],
): Record<string, StrategyVersionDiff[]> {
  const groups: Record<string, StrategyVersionDiff[]> = {};
  for (const d of diffs) {
    let placed = false;
    for (const section of SECTION_PREFIXES) {
      if (section.matches(d.field_path)) {
        (groups[section.key] ??= []).push(d);
        placed = true;
        break;
      }
    }
    if (!placed) (groups["__other__"] ??= []).push(d);
  }
  return groups;
}

function formatValue(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
