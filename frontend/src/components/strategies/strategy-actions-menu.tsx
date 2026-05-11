"use client";

/**
 * 3-dot actions menu for a strategy row.
 *
 * Used in two places:
 *   * ``variant="card"``   — strategies list page, compact ghost trigger.
 *   * ``variant="detail"`` — strategy detail page, alongside View Backtest.
 *
 * Actions and their wire calls:
 *   * Edit       → router.push to expert builder with ?edit=<id>.
 *   * Duplicate  → GET /strategies/{id} → POST /strategies with a fresh
 *                  copy ( "(copy)" name suffix, blob's inner ``id``
 *                  regenerated so the canonical schema check doesn't
 *                  trip on duplicate ids).
 *   * Archive    → PATCH /strategies/{id}/active toggling is_active.
 *   * Delete     → opens an inline confirmation Dialog, then DELETE.
 *
 * Legacy strategies (``strategy_json: null``) cannot be edited or
 * duplicated — those rows were created before the Phase 5 DSL and have
 * nothing the builder can rehydrate. Archive + Delete still work.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  MoreHorizontal,
  Pencil,
  Copy,
  Archive,
  ArchiveRestore,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
// The Base UI Menu binding renders its own trigger button and does
// not accept a Radix-style ``asChild`` prop — apply button-like
// classes directly on ``DropdownMenuTrigger`` instead (see
// ``components/dashboard/top-bar.tsx`` for the same pattern).
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface StrategySummary {
  id: string;
  name: string;
  is_active: boolean;
  strategy_json: Record<string, unknown> | null;
}

interface StrategyActionsMenuProps {
  strategy: StrategySummary;
  variant: "card" | "detail";
  /** Called after a successful mutation so the parent can refetch. */
  onChanged: () => void;
  /** When true, after a Delete the menu navigates to ``/strategies``
   *  (used on the detail page; the list page just refetches in place). */
  redirectAfterDelete?: boolean;
}

interface CreatedStrategyResponse {
  id: string;
  name: string;
}

export function StrategyActionsMenu({
  strategy,
  variant,
  onChanged,
  redirectAfterDelete = false,
}: StrategyActionsMenuProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [working, setWorking] = useState<
    null | "duplicate" | "archive" | "delete"
  >(null);

  const hasDsl = !!strategy.strategy_json;

  function handleEdit() {
    if (!hasDsl) {
      toast.info(
        "Yeh legacy strategy hai (no DSL). Edit ke liye ek nayi strategy bana lo.",
      );
      return;
    }
    router.push(`/strategies/new/expert?edit=${strategy.id}`);
  }

  async function handleDuplicate() {
    if (!hasDsl) {
      toast.info("Legacy strategy duplicate nahi ho sakti — DSL nahi hai.");
      return;
    }
    setWorking("duplicate");
    try {
      // Fetch the full row so we have the latest blob (the list endpoint
      // already returns ``strategy_json`` but the detail call is
      // authoritative — versions etc. live there).
      const full = await api.get<StrategySummary>(
        `/strategies/${strategy.id}`,
      );
      if (!full.strategy_json) {
        toast.error("Duplicate nahi ho payi: source DSL nahi mila.");
        return;
      }
      const copyBlob: Record<string, unknown> = { ...full.strategy_json };
      // The canonical StrategyJSON carries its own ``id`` and ``name``
      // fields. Reset them — the backend assigns a fresh row UUID and
      // we suffix the name so users can tell copies apart.
      const suffixedName = `${full.name} (copy)`;
      copyBlob.name = suffixedName;
      // Regenerate inner DSL id if present so the canonical schema's
      // "unique id" check downstream doesn't flag collisions.
      if (typeof copyBlob.id === "string") {
        copyBlob.id = makeRandomId();
      }
      const created = await api.post<CreatedStrategyResponse>("/strategies", {
        strategy_json: copyBlob,
      });
      toast.success(`Duplicated as "${created.name}".`);
      onChanged();
      router.push(`/strategies/${created.id}`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Duplicate nahi ho payi. Network ya backend issue.";
      toast.error(msg);
    } finally {
      setWorking(null);
    }
  }

  async function handleArchiveToggle() {
    setWorking("archive");
    const next = !strategy.is_active;
    try {
      await api.patch<StrategySummary>(
        `/strategies/${strategy.id}/active`,
        { is_active: next },
      );
      toast.success(
        next
          ? `"${strategy.name}" activated.`
          : `"${strategy.name}" archived.`,
      );
      onChanged();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Status update nahi hua. Network ya backend issue.";
      toast.error(msg);
    } finally {
      setWorking(null);
    }
  }

  async function handleDeleteConfirmed() {
    setWorking("delete");
    try {
      await api.delete<void>(`/strategies/${strategy.id}`);
      toast.success(`"${strategy.name}" deleted.`);
      setConfirmOpen(false);
      if (redirectAfterDelete) {
        router.push("/strategies");
      } else {
        onChanged();
      }
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Delete nahi ho payi. Network ya backend issue.";
      toast.error(msg);
    } finally {
      setWorking(null);
    }
  }

  const triggerLabel = `Actions for ${strategy.name}`;
  const triggerClass = cn(
    "inline-flex items-center justify-center gap-1 whitespace-nowrap rounded-md text-sm font-medium transition-colors",
    "hover:bg-accent hover:text-accent-foreground cursor-pointer",
    "disabled:pointer-events-none disabled:opacity-50",
    variant === "card" ? "h-8 w-8" : "h-8 px-2.5",
  );

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={triggerLabel}
          disabled={working !== null}
          className={triggerClass}
        >
          <MoreHorizontal className="h-4 w-4" />
          {variant === "detail" ? (
            <span className="text-xs">Actions</span>
          ) : null}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem
            onClick={handleEdit}
            disabled={!hasDsl}
            className="cursor-pointer"
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={handleDuplicate}
            disabled={!hasDsl || working === "duplicate"}
            className="cursor-pointer"
          >
            <Copy className="h-3.5 w-3.5" />
            {working === "duplicate" ? "Duplicating…" : "Duplicate"}
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={handleArchiveToggle}
            disabled={working === "archive"}
            className="cursor-pointer"
          >
            {strategy.is_active ? (
              <>
                <Archive className="h-3.5 w-3.5" />
                {working === "archive" ? "Archiving…" : "Archive"}
              </>
            ) : (
              <>
                <ArchiveRestore className="h-3.5 w-3.5" />
                {working === "archive" ? "Activating…" : "Unarchive"}
              </>
            )}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setConfirmOpen(true)}
            className="cursor-pointer text-loss focus:text-loss"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-loss" />
              Delete strategy?
            </DialogTitle>
            <DialogDescription className="pt-2 text-sm">
              Delete <span className="font-semibold">{strategy.name}</span>?
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setConfirmOpen(false)}
              disabled={working === "delete"}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={handleDeleteConfirmed}
              disabled={working === "delete"}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {working === "delete" ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function makeRandomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}
