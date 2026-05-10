"use client";

/**
 * Standalone Risk Builder — author one ``RiskRules`` block in
 * isolation and save it as a reusable template.
 *
 * Reuses the Expert Builder's ``RiskState`` shape + ``RISK_RANGES``
 * constants from ``builder-types.ts`` so the field bounds stay in
 * sync. The page renders its own focused 4-input grid rather than
 * the Expert ``RiskSection`` — that section bundles a Robustness
 * Test toggle which is a backtest concern, not a risk-template
 * concern.
 *
 * The Expert / Beginner / Intermediate builders, plus the
 * Standalone Entry / Exit Builders, are NOT touched.
 */

import { useReducer, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  BookmarkPlus,
  FilePlus2,
  Save,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { toast } from "sonner";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

import {
  RISK_RANGES,
  type RiskState,
  INITIAL_RISK,
} from "@/components/strategies/expert-builder/builder-types";
import {
  RiskTemplateCard,
  type RiskTemplateCardData,
} from "@/components/strategies/risk-template-card";

// ─── Presets ───────────────────────────────────────────────────────────

interface RiskPreset {
  id: "conservative" | "moderate" | "aggressive";
  label: string;
  blurb: string;
  state: RiskState;
}

const PRESETS: ReadonlyArray<RiskPreset> = [
  {
    id: "conservative",
    label: "Conservative",
    blurb: "Tight caps — naya trader ya choti capital ke liye",
    state: {
      maxDailyLossPercent: "2",
      maxTradesPerDay: "3",
      maxLossStreak: "2",
      maxCapitalPerTradePercent: "5",
    },
  },
  {
    id: "moderate",
    label: "Moderate",
    blurb: "Balanced caps — disciplined day-trader ke liye",
    state: {
      maxDailyLossPercent: "3",
      maxTradesPerDay: "5",
      maxLossStreak: "3",
      maxCapitalPerTradePercent: "10",
    },
  },
  {
    id: "aggressive",
    label: "Aggressive",
    blurb: "Wider caps — high-conviction setups ke liye, risk samjho",
    state: {
      maxDailyLossPercent: "5",
      maxTradesPerDay: "10",
      maxLossStreak: "5",
      maxCapitalPerTradePercent: "25",
    },
  },
];

// ─── State machine ─────────────────────────────────────────────────────

interface BuilderState {
  risk: RiskState;
  loadedTemplateId: string | null;
}

const INITIAL_STATE: BuilderState = {
  risk: INITIAL_RISK,
  loadedTemplateId: null,
};

type Action =
  | { type: "set_field"; key: keyof RiskState; value: string }
  | { type: "apply_preset"; preset: RiskPreset }
  | { type: "load_template"; payload: BuilderState }
  | { type: "reset" };

function reducer(state: BuilderState, action: Action): BuilderState {
  switch (action.type) {
    case "set_field":
      return {
        ...state,
        risk: { ...state.risk, [action.key]: action.value },
      };
    case "apply_preset":
      return { ...state, risk: { ...action.preset.state } };
    case "load_template":
      return action.payload;
    case "reset":
      return INITIAL_STATE;
  }
}

// ─── Wire types ────────────────────────────────────────────────────────

interface RiskTemplateListResponse {
  templates: RiskTemplateCardData[];
  count: number;
}

// ─── Page ──────────────────────────────────────────────────────────────

export default function StandaloneRiskBuilderPage() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const {
    data: templatesResp,
    refetch: refetchTemplates,
  } = useApi<RiskTemplateListResponse>("/templates/risk", {
    templates: [],
    count: 0,
  });

  // Empty risk_rules is valid server-side (all caps optional). The
  // only client-side gate is name + not-submitting; let the backend
  // catch range violations (gt=0, le=100) on save.
  const canSave = name.trim().length > 0 && !submitting;

  async function handleSave() {
    if (!canSave) return;
    setSubmitting(true);
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        risk_rules: toWireRiskRules(state.risk),
      };
      if (state.loadedTemplateId) {
        await api.put(`/templates/risk/${state.loadedTemplateId}`, body);
        toast.success("Template update ho gaya 🎉");
      } else {
        await api.post("/templates/risk", body);
        toast.success("Template save ho gaya 🎉");
      }
      refetchTemplates();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Template save nahi ho paya — refresh karke try karo.";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  function handleLoad(template: RiskTemplateCardData) {
    setName(template.name);
    setDescription(template.description ?? "");
    dispatch({ type: "load_template", payload: hydrateTemplate(template) });
    toast.message(`"${template.name}" load ho gaya — edit karke save karo`);
  }

  async function handleDelete(templateId: string) {
    try {
      await api.delete(`/templates/risk/${templateId}`);
      if (state.loadedTemplateId === templateId) {
        dispatch({ type: "reset" });
        setName("");
        setDescription("");
      }
      refetchTemplates();
      toast.success("Template delete ho gaya");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.detail : "Delete nahi ho paya";
      toast.error(msg);
    }
  }

  function handleNewBlank() {
    dispatch({ type: "reset" });
    setName("");
    setDescription("");
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-5"
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
            <Workflow className="h-6 w-6 text-accent-blue" />
            Risk Management Builder
          </h1>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Sirf risk rules banao — apne paise ko safe rakho. Daily
            loss cap, trades-per-day, capital per trade — sab yahan
            hai. Beginner / Intermediate / Expert builders mein baad
            mein apply kar sakte ho. ✨
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleNewBlank}
          type="button"
        >
          <FilePlus2 className="h-3.5 w-3.5" />
          New blank
        </Button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* Editor column */}
        <div className="space-y-4">
          {/* Presets */}
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent-purple" />
                <h3 className="text-sm font-semibold">Quick presets</h3>
                <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                  Fill defaults, edit baad mein
                </Badge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {PRESETS.map((preset) => (
                  <PresetButton
                    key={preset.id}
                    preset={preset}
                    onApply={() => {
                      dispatch({ type: "apply_preset", preset });
                      toast.message(
                        `${preset.label} preset apply ho gaya — naam do aur save karo`,
                      );
                    }}
                  />
                ))}
              </div>
            </div>
          </GlassmorphismCard>

          {/* Risk Caps */}
          <GlassmorphismCard hover={false}>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-accent-blue" />
                <h2 className="font-semibold">Risk Caps</h2>
                <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                  All optional
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Khaali chhodoge to cap apply nahi hota. Range out-of-bounds
                value pe save 422 dega — backend canonical
                ``RiskRules`` se validate karta hai.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <RiskField
                  label="Max Daily Loss %"
                  help={`${RISK_RANGES.maxDailyLossPercent.min}–${RISK_RANGES.maxDailyLossPercent.max}%`}
                  value={state.risk.maxDailyLossPercent}
                  min={RISK_RANGES.maxDailyLossPercent.min}
                  max={RISK_RANGES.maxDailyLossPercent.max}
                  onChange={(v) =>
                    dispatch({
                      type: "set_field",
                      key: "maxDailyLossPercent",
                      value: v,
                    })
                  }
                />
                <RiskField
                  label="Max Trades / Day"
                  help={`${RISK_RANGES.maxTradesPerDay.min}–${RISK_RANGES.maxTradesPerDay.max}`}
                  value={state.risk.maxTradesPerDay}
                  min={RISK_RANGES.maxTradesPerDay.min}
                  max={RISK_RANGES.maxTradesPerDay.max}
                  integer
                  onChange={(v) =>
                    dispatch({
                      type: "set_field",
                      key: "maxTradesPerDay",
                      value: v,
                    })
                  }
                />
                <RiskField
                  label="Max Loss Streak"
                  help={`${RISK_RANGES.maxLossStreak.min}–${RISK_RANGES.maxLossStreak.max} consecutive losses`}
                  value={state.risk.maxLossStreak}
                  min={RISK_RANGES.maxLossStreak.min}
                  max={RISK_RANGES.maxLossStreak.max}
                  integer
                  onChange={(v) =>
                    dispatch({
                      type: "set_field",
                      key: "maxLossStreak",
                      value: v,
                    })
                  }
                />
                <RiskField
                  label="Max Capital / Trade %"
                  help={`${RISK_RANGES.maxCapitalPerTradePercent.min}–${RISK_RANGES.maxCapitalPerTradePercent.max}%`}
                  value={state.risk.maxCapitalPerTradePercent}
                  min={RISK_RANGES.maxCapitalPerTradePercent.min}
                  max={RISK_RANGES.maxCapitalPerTradePercent.max}
                  onChange={(v) =>
                    dispatch({
                      type: "set_field",
                      key: "maxCapitalPerTradePercent",
                      value: v,
                    })
                  }
                />
              </div>
            </div>
          </GlassmorphismCard>

          {/* Save form */}
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Save className="h-4 w-4 text-accent-blue" />
                <h3 className="font-semibold text-sm">
                  {state.loadedTemplateId
                    ? "Update template"
                    : "Save as template"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-3">
                <div className="space-y-1">
                  <label
                    htmlFor="risk-template-name"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Template Name *
                  </label>
                  <Input
                    id="risk-template-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="My moderate caps"
                    maxLength={128}
                  />
                </div>
                <div className="space-y-1">
                  <label
                    htmlFor="risk-template-desc"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Description (optional)
                  </label>
                  <Input
                    id="risk-template-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Kya situation mein use karna hai..."
                    maxLength={2000}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p
                  className={cn(
                    "text-[11px]",
                    canSave ? "text-profit" : "text-muted-foreground",
                  )}
                >
                  {canSave
                    ? "Looks good — save karne ke liye ready hai"
                    : !name.trim()
                      ? "Template ka name daalo"
                      : "Saving..."}
                </p>
                <GlowButton
                  size="sm"
                  onClick={handleSave}
                  disabled={!canSave}
                  type="button"
                >
                  <BookmarkPlus className="h-3.5 w-3.5" />
                  {state.loadedTemplateId
                    ? "Update Template"
                    : "Save Template"}
                </GlowButton>
              </div>
            </div>
          </GlassmorphismCard>
        </div>

        {/* Templates sidebar */}
        <aside className="space-y-3 lg:sticky lg:top-4 self-start">
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <header className="space-y-1">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-accent-purple" />
                  Saved Templates
                </h3>
                <p className="text-[10px] text-muted-foreground">
                  Click to load. Edit karke update karo, ya delete karo.
                </p>
              </header>
              {templatesResp && templatesResp.count > 0 ? (
                <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
                  {templatesResp.templates.map((tpl) => (
                    <RiskTemplateCard
                      key={tpl.id}
                      template={tpl}
                      active={tpl.id === state.loadedTemplateId}
                      onLoad={handleLoad}
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 text-[11px] text-muted-foreground leading-relaxed">
                  Abhi koi saved template nahi. Preset choose karo ya
                  fields fill karo, naam do, phir save karo. Yeh
                  sidebar populate ho jayega.
                </div>
              )}
              {state.loadedTemplateId ? (
                <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
                  Editing template
                </Badge>
              ) : null}
            </div>
          </GlassmorphismCard>
        </aside>
      </div>
    </motion.div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────

function PresetButton({
  preset,
  onApply,
}: {
  preset: RiskPreset;
  onApply: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onApply}
      className={cn(
        "rounded-lg border p-3 text-left transition-colors",
        "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] hover:border-accent-blue/30",
      )}
    >
      <div className="text-sm font-semibold">{preset.label}</div>
      <p className="text-[10px] text-muted-foreground leading-relaxed mt-0.5">
        {preset.blurb}
      </p>
    </button>
  );
}

function RiskField({
  label,
  help,
  value,
  min,
  max,
  integer = false,
  onChange,
}: {
  label: string;
  help: string;
  value: string;
  min: number;
  max: number;
  integer?: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={integer ? 1 : "any"}
        placeholder="No cap"
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "w-full rounded-md px-2.5 py-1.5 text-sm",
          "bg-white/[0.02] border border-white/[0.06] text-foreground",
          "placeholder:text-muted-foreground",
          "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
        )}
      />
      <p className="text-[10px] text-muted-foreground">{help}</p>
    </div>
  );
}

// ─── Helpers — translate between wire shape and builder state ────────

function parseOptionalNumber(raw: string): number | undefined {
  const t = raw.trim();
  if (t === "") return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

function toWireRiskRules(risk: RiskState): Record<string, unknown> {
  // camelCase keys — match the ``RiskRules`` Pydantic aliases.
  // Empty / non-numeric fields are dropped so the persisted JSON
  // stays compact and matches the canonical "no cap" semantic.
  const out: Record<string, unknown> = {};
  const dl = parseOptionalNumber(risk.maxDailyLossPercent);
  const tpd = parseOptionalNumber(risk.maxTradesPerDay);
  const ls = parseOptionalNumber(risk.maxLossStreak);
  const cap = parseOptionalNumber(risk.maxCapitalPerTradePercent);
  if (dl !== undefined) out.maxDailyLossPercent = dl;
  if (tpd !== undefined) out.maxTradesPerDay = tpd;
  if (ls !== undefined) out.maxLossStreak = ls;
  if (cap !== undefined) out.maxCapitalPerTradePercent = cap;
  return out;
}

function hydrateTemplate(template: RiskTemplateCardData): BuilderState {
  const wire = (template.risk_rules ?? {}) as Record<string, unknown>;
  return {
    risk: {
      maxDailyLossPercent:
        typeof wire.maxDailyLossPercent === "number"
          ? String(wire.maxDailyLossPercent)
          : "",
      maxTradesPerDay:
        typeof wire.maxTradesPerDay === "number"
          ? String(wire.maxTradesPerDay)
          : "",
      maxLossStreak:
        typeof wire.maxLossStreak === "number"
          ? String(wire.maxLossStreak)
          : "",
      maxCapitalPerTradePercent:
        typeof wire.maxCapitalPerTradePercent === "number"
          ? String(wire.maxCapitalPerTradePercent)
          : "",
    },
    loadedTemplateId: template.id,
  };
}
