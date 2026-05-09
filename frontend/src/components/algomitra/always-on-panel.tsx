"use client";

/**
 * Always-On AlgoMitra side panel — Phase 1 of the May-18 launch plan.
 *
 * Auto-mounts on the three Builder routes (Beginner / Intermediate /
 * Expert) and renders pre-defined Hinglish coaching tips per builder
 * tier. Coexists with the existing :class:`ChatWidget` — that one
 * floats bottom-right for free-form chat; this one anchors right-side
 * for continuous coaching.
 *
 * Phase 2 (next session) wires per-section reactivity via a shared
 * React context the Builder pages can opt into. For now the panel
 * shows all sections accordion-style with the first tip per section
 * visible by default; the user expands a section to see more.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  Mic,
  Settings,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  COACHING_TIPS,
  WELCOME_MESSAGES,
  type BuilderMode,
  type BuilderSection,
  type CoachingSection,
} from "./coaching-tips-data";
import {
  useAlgoMitraContext,
  useAlgoMitraPanelState,
} from "@/hooks/use-algomitra-context";
import { AlgoMitraToggleButton } from "./toggle-button";

// ── Component ──────────────────────────────────────────────────────────

export function AlwaysOnAlgoMitraPanel() {
  const { isBuilderRoute, mode } = useAlgoMitraContext();
  const { isOpen, close, open } = useAlgoMitraPanelState();

  // Render only on the three Builder routes. Other pages keep the
  // existing ChatWidget as the only AlgoMitra surface.
  if (!isBuilderRoute || mode === null) return null;

  // ``useSyncExternalStore`` handles SSR/CSR snapshot reconciliation
  // without an explicit mounted-flag — the server snapshot is "open"
  // and the client snapshot reads ``localStorage``; React reconciles
  // the mismatch on the first commit without flashing the wrong
  // state at the user.

  return (
    <>
      <AnimatePresence>
        {isOpen ? <PanelBody mode={mode} onClose={close} /> : null}
      </AnimatePresence>
      <AnimatePresence>
        {!isOpen ? <AlgoMitraToggleButton onClick={open} /> : null}
      </AnimatePresence>
    </>
  );
}

// ── Panel body ─────────────────────────────────────────────────────────

interface PanelBodyProps {
  mode: BuilderMode;
  onClose: () => void;
}

function PanelBody({ mode, onClose }: PanelBodyProps) {
  const { user } = useAuth();
  const greetingName = user?.full_name || user?.email?.split("@")[0] || "Trader";

  const tipsForMode = COACHING_TIPS[mode];
  const sections = Object.entries(tipsForMode) as Array<
    [BuilderSection, CoachingSection]
  >;

  // First section expanded by default — gives the user something
  // useful at-a-glance without forcing them to click.
  const [expanded, setExpanded] = useState<BuilderSection | null>(
    (sections[0]?.[0] as BuilderSection) ?? null,
  );

  return (
    <motion.aside
      key="algomitra-panel"
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 320, opacity: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "fixed right-0 top-16 z-40",
        "h-[calc(100vh-5rem)]",
        "w-full max-w-[320px] md:max-w-[320px]",
        "rounded-l-2xl border-l border-y border-white/[0.08]",
        "bg-popover/95 backdrop-blur-xl shadow-[0_0_60px_rgba(168,85,247,0.18)]",
        "flex flex-col overflow-hidden",
      )}
      role="complementary"
      aria-label="AlgoMitra coaching panel"
    >
      <PanelHeader greetingName={greetingName} onClose={onClose} />
      <PanelWelcome mode={mode} />
      <PanelTips
        sections={sections}
        expanded={expanded}
        onToggle={(section) =>
          setExpanded((prev) => (prev === section ? null : section))
        }
      />
      <PanelFooter />
    </motion.aside>
  );
}

// ── Sub-pieces ─────────────────────────────────────────────────────────

function PanelHeader({
  greetingName,
  onClose,
}: {
  greetingName: string;
  onClose: () => void;
}) {
  return (
    <header className="flex items-start justify-between gap-3 p-3 border-b border-white/[0.06]">
      <div className="flex items-center gap-2 min-w-0">
        <div className="size-7 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple grid place-items-center shrink-0">
          <Bot className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold truncate">AlgoMitra Coach</h2>
          <p className="text-[10px] text-muted-foreground truncate">
            {greetingName}
          </p>
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onClose}
        type="button"
        aria-label="Close AlgoMitra panel"
      >
        <X className="h-4 w-4" />
      </Button>
    </header>
  );
}

function PanelWelcome({ mode }: { mode: BuilderMode }) {
  return (
    <div className="px-3 py-3 border-b border-white/[0.06]">
      <p className="text-xs leading-relaxed">{WELCOME_MESSAGES[mode]}</p>
    </div>
  );
}

interface PanelTipsProps {
  sections: Array<[BuilderSection, CoachingSection]>;
  expanded: BuilderSection | null;
  onToggle: (section: BuilderSection) => void;
}

function PanelTips({ sections, expanded, onToggle }: PanelTipsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
      {sections.map(([sectionId, content]) => (
        <TipsSection
          key={sectionId}
          sectionId={sectionId}
          content={content}
          expanded={expanded === sectionId}
          onToggle={() => onToggle(sectionId)}
        />
      ))}
    </div>
  );
}

function TipsSection({
  sectionId,
  content,
  expanded,
  onToggle,
}: {
  sectionId: BuilderSection;
  content: CoachingSection;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <section
      className={cn(
        "rounded-lg border bg-white/[0.02] transition-colors",
        expanded
          ? "border-accent-purple/30 bg-accent-purple/[0.05]"
          : "border-white/[0.06] hover:bg-white/[0.03]",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-2 px-2.5 py-2 text-left"
        aria-expanded={expanded}
        aria-controls={`algomitra-tips-${sectionId}`}
      >
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold">
          <Lightbulb className="h-3 w-3 text-accent-purple" />
          {content.title}
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>
      {expanded ? (
        <ul
          id={`algomitra-tips-${sectionId}`}
          className="px-2.5 pb-2.5 space-y-1.5"
        >
          {content.tips.map((tip, idx) => (
            <li
              key={idx}
              className="text-[11px] leading-relaxed flex items-start gap-1.5"
            >
              <span className="text-accent-purple shrink-0">💡</span>
              <span>{tip}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function PanelFooter() {
  return (
    <footer className="border-t border-white/[0.06] p-2 flex items-center justify-between gap-2">
      <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
        <Mic className="h-2.5 w-2.5 mr-0.5" />
        Voice ✨ coming soon
      </Badge>
      <Button
        variant="ghost"
        size="sm"
        type="button"
        disabled
        className="text-[10px]"
        title="Settings — coming soon"
      >
        <Settings className="h-3 w-3" />
        Settings
      </Button>
    </footer>
  );
}

// ── Layout-level mount alias ──────────────────────────────────────────

/** Layout-level export. ``useSyncExternalStore`` already handles
 *  SSR/CSR consistency, so the wrapper is just a stable name the
 *  layout imports — keeps the layout's import diff small if the
 *  inner component is ever renamed. */
export const AlwaysOnAlgoMitraPanelMount = AlwaysOnAlgoMitraPanel;
