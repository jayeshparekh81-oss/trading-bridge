"use client";

import Link from "next/link";
import {
  ScanEye,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ShieldQuestion,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ConvertedStrategyView } from "./converted-strategy-view";
import type { LicenseStatus, PineImportResponse } from "./types";


type PanelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "result"; response: PineImportResponse };


interface ResultPanelProps {
  state: PanelState;
  onSave: () => void;
  onSavePartial: () => void;
  saving: boolean;
}

export function ResultPanel({
  state,
  onSave,
  onSavePartial,
  saving,
}: ResultPanelProps) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ScanEye className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Conversion Result</h2>
        </div>

        {state.kind === "idle" ? (
          <IdleState />
        ) : state.kind === "loading" ? (
          <LoadingState />
        ) : state.kind === "error" ? (
          <ErrorState message={state.message} />
        ) : state.response.success ? (
          <SuccessState
            response={state.response}
            onSave={onSave}
            saving={saving}
          />
        ) : state.response.partial && state.response.converted ? (
          <PartialState
            response={state.response}
            onSavePartial={onSavePartial}
            saving={saving}
          />
        ) : (
          <FailureState response={state.response} />
        )}
      </div>
    </GlassmorphismCard>
  );
}


// ─── States ────────────────────────────────────────────────────────────


function IdleState() {
  return (
    <div className="text-center py-12 space-y-3 text-muted-foreground">
      <ScanEye className="h-12 w-12 mx-auto opacity-30" />
      <p className="text-sm">Paste Pine script and click Convert.</p>
    </div>
  );
}


function LoadingState() {
  return (
    <div className="text-center py-12 space-y-3">
      <Loader2 className="h-10 w-10 text-accent-blue mx-auto animate-spin" />
      <p className="text-sm font-medium">Convert ho raha hai...</p>
      <p className="text-[11px] text-muted-foreground">
        Lexer, parser, mapper chalu hain. Pure-Python, koi network call nahi.
      </p>
    </div>
  );
}


function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg bg-loss/[0.08] border border-loss/30 px-3 py-3 flex items-start gap-2">
      <AlertTriangle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-loss">Convert fail ho gaya</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">{message}</p>
      </div>
    </div>
  );
}


function SuccessState({
  response,
  onSave,
  saving,
}: {
  response: Extract<PineImportResponse, { success: true }>;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className="bg-profit/15 text-profit border-profit/30 gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Converted ✅
        </Badge>
        <LicenseBadge status={response.license_status} />
      </div>

      <div className="rounded-lg bg-accent-blue/[0.06] border border-accent-blue/20 p-3 flex items-start gap-2">
        <Sparkles className="h-4 w-4 text-accent-blue shrink-0 mt-0.5" />
        <div className="text-[13px] leading-relaxed">{response.explanation}</div>
      </div>

      <ConvertedStrategyView strategy={response.strategy} />

      {response.notes.length > 0 ? (
        <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
            Notes
          </p>
          <ul className="text-[11px] text-muted-foreground space-y-0.5">
            {response.notes.map((n, i) => (
              <li key={i}>• {n}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex justify-end">
        <GlowButton onClick={onSave} disabled={saving} size="md">
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4 mr-2" />
              Save as Strategy
            </>
          )}
        </GlowButton>
      </div>
    </div>
  );
}


function PartialState({
  response,
  onSavePartial,
  saving,
}: {
  response: Extract<PineImportResponse, { success: false }>;
  onSavePartial: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className="bg-yellow-500/15 text-yellow-200 border-yellow-500/40 gap-1">
          <AlertTriangle className="h-3 w-3" />
          Partial conversion ⚠️
        </Badge>
        <LicenseBadge status={response.license_status} />
      </div>

      <div className="rounded-lg bg-yellow-500/[0.06] border border-yellow-500/30 p-3 space-y-2">
        <p className="text-[12px] leading-relaxed text-yellow-100">
          {response.message}
        </p>
        {response.unsupported.length > 0 ? (
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium mb-1">
              Unsupported
            </p>
            <ul className="text-[11px] text-muted-foreground space-y-0.5">
              {response.unsupported.map((u, i) => (
                <li key={i}>
                  • <span className="font-mono">{u}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {response.converted ? (
        <ConvertedStrategyView strategy={response.converted} />
      ) : null}

      <div className="flex items-center justify-between gap-3 flex-wrap pt-1">
        <p className="text-[11px] text-muted-foreground">
          Save partial — phir expert builder mein missing pieces add karo.
        </p>
        <GlowButton
          onClick={onSavePartial}
          disabled={saving || !response.converted}
          variant="profit"
          size="md"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4 mr-2" />
              Save partial
            </>
          )}
        </GlowButton>
      </div>
    </div>
  );
}


function FailureState({
  response,
}: {
  response: Extract<PineImportResponse, { success: false }>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className="bg-loss/15 text-loss border-loss/30 gap-1">
          <XCircle className="h-3 w-3" />
          Convert nahi ho saka ❌
        </Badge>
        <LicenseBadge status={response.license_status} />
      </div>

      <div className="rounded-lg bg-loss/[0.06] border border-loss/30 p-3 space-y-2">
        <p className="text-[12px] leading-relaxed text-loss/90">
          {response.message}
        </p>
        {response.unsupported.length > 0 ? (
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium mb-1">
              Yeh features support nahi hain
            </p>
            <ul className="text-[11px] text-muted-foreground space-y-0.5">
              {response.unsupported.map((u, i) => (
                <li key={i}>
                  • <span className="font-mono">{u}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <div className="rounded-md bg-white/[0.02] border border-white/[0.04] px-3 py-3 flex items-center gap-3">
        <Sparkles className="h-4 w-4 text-accent-blue shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-medium">Manual builder use karo</p>
          <p className="text-[11px] text-muted-foreground">
            Expert builder mein full DSL access hai — Pine ke unsupported parts
            ko hand-code karo.
          </p>
        </div>
        <Link
          href="/strategies/new/expert"
          className={cn(
            "inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md",
            "bg-accent-blue/15 border border-accent-blue/30 text-accent-blue",
            "hover:bg-accent-blue/25 transition-colors font-medium",
          )}
        >
          Open Builder
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}


// ─── License badge ────────────────────────────────────────────────────


function LicenseBadge({ status }: { status: LicenseStatus }) {
  switch (status) {
    case "permissive":
      return (
        <Badge className="bg-profit/15 text-profit border-profit/30 gap-1">
          <CheckCircle2 className="h-3 w-3" />
          License: permissive
        </Badge>
      );
    case "compliance_required":
      return (
        <Badge className="bg-yellow-500/15 text-yellow-200 border-yellow-500/30 gap-1">
          <ShieldQuestion className="h-3 w-3" />
          License: compliance required
        </Badge>
      );
    case "needs_review":
      return (
        <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 gap-1">
          <ShieldQuestion className="h-3 w-3" />
          License: needs review
        </Badge>
      );
    case "blocked":
      return (
        <Badge className="bg-loss/15 text-loss border-loss/30 gap-1">
          <XCircle className="h-3 w-3" />
          License: blocked
        </Badge>
      );
  }
}
