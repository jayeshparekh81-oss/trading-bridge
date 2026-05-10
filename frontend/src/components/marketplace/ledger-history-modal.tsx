"use client";

/**
 * Paginated snapshot history modal. Lists every snapshot for a
 * listing, newest first. Each row shows the date, sequence number,
 * cumulative PnL, max drawdown, and a truncated chain signature.
 * Click a row to expand the full snapshot payload + hash details.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import type { LedgerSnapshot } from "./transparency-ledger-panel";

interface LedgerHistoryResponse {
  snapshots: LedgerSnapshot[];
  count: number;
}

interface LedgerHistoryModalProps {
  listingId: string;
  open: boolean;
  onClose: () => void;
}

export function LedgerHistoryModal({
  listingId,
  open,
  onClose,
}: LedgerHistoryModalProps) {
  const { data, isLoading } = useApi<LedgerHistoryResponse>(
    open ? `/marketplace/listings/${listingId}/ledger/history?limit=50` : null,
    { snapshots: [], count: 0 },
  );

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.96, y: 8 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.96, y: 8 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className="bg-[#0b0e14] border border-white/[0.08] rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-center justify-between p-4 border-b border-white/[0.06]">
              <div className="space-y-0.5">
                <h3 className="text-sm font-semibold">Ledger History</h3>
                <p className="text-[10px] text-muted-foreground">
                  Newest snapshots top par. Click karke details kholo.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                type="button"
              >
                <X className="h-4 w-4" />
              </Button>
            </header>
            <div className="overflow-y-auto max-h-[calc(80vh-72px)] p-4">
              {isLoading ? (
                <p className="text-[11px] text-muted-foreground">
                  History load ho rahi hai…
                </p>
              ) : data && data.count > 0 ? (
                <div className="space-y-2">
                  {data.snapshots.map((snap) => (
                    <SnapshotRow key={snap.id} snapshot={snap} />
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  Abhi tak koi snapshot nahi liya gaya. Creator daily
                  trigger chala kar chain start karega.
                </p>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function SnapshotRow({ snapshot }: { snapshot: LedgerSnapshot }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="w-full text-left rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-colors p-3 space-y-2"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
            #{snapshot.sequence_number}
          </Badge>
          <span className="text-xs font-medium">{snapshot.snapshot_date}</span>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span
            className={cn(
              snapshot.cumulative_pnl_inr >= 0 ? "text-profit" : "text-loss",
            )}
          >
            ₹{snapshot.cumulative_pnl_inr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </span>
          <span className="text-muted-foreground">
            DD {snapshot.max_drawdown_pct.toFixed(1)}%
          </span>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
          />
        </div>
      </div>
      {expanded ? (
        <div className="rounded-md bg-black/30 border border-white/[0.04] p-2.5 space-y-1.5 text-[10px] font-mono leading-relaxed">
          <div>
            <span className="text-muted-foreground">data_hash: </span>
            <span className="break-all">{snapshot.data_hash}</span>
          </div>
          <div>
            <span className="text-muted-foreground">prior_hash: </span>
            <span className="break-all">
              {snapshot.prior_hash ?? "(genesis)"}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">chain_signature: </span>
            <span className="break-all">{snapshot.chain_signature}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 pt-1.5 border-t border-white/[0.04]">
            <span>
              Trades: {snapshot.total_trades} (paper{" "}
              {snapshot.paper_trades_count} / live {snapshot.live_trades_count})
            </span>
            <span>Win rate: {(snapshot.win_rate * 100).toFixed(1)}%</span>
            <span>
              Days since publish: {snapshot.days_since_publish}
            </span>
            <span>
              Sharpe: {snapshot.sharpe_ratio == null ? "—" : snapshot.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        </div>
      ) : null}
    </button>
  );
}
