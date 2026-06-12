"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  Sparkles,
  Lock,
  CheckCircle2,
  FlaskConical,
  GraduationCap,
  Cpu,
  Layers,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { IndicatorVerificationBadge } from "@/components/indicators/IndicatorVerificationBadge";
import {
  STRATEGY_MODE_STORAGE_KEY,
  type StrategyMode,
} from "@/components/strategies/mode-selector";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

/**
 * Frontend type mirroring ``IndicatorMetadata`` from the backend
 * (camelCase aliases honoured by Pydantic's ``populate_by_name``).
 */
export interface IndicatorMetadata {
  id: string;
  name: string;
  category: string;
  description: string;
  inputs: ReadonlyArray<unknown>;
  outputs: string[];
  chartType: "overlay" | "separate";
  pineAliases: string[];
  difficulty: "beginner" | "intermediate" | "expert";
  status: "active" | "coming_soon" | "experimental";
  aiExplanation: string;
  tags: string[];
  calculationFunction?: string | null;
}

interface IndicatorLibraryProps {
  indicators: ReadonlyArray<IndicatorMetadata>;
}

/**
 * Resolve which indicators the current authoring mode allows. The
 * mode lives in the same localStorage key as the dashboard's
 * :class:`ModeSelector`, so the two surfaces stay in sync.
 *
 *   beginner     → BEGINNER difficulty + ACTIVE only
 *   intermediate → ACTIVE indicators of any difficulty
 *   expert       → ACTIVE + EXPERIMENTAL of any difficulty
 *
 * COMING_SOON entries are *visible to every mode* — they render as
 * disabled cards so the user knows the catalogue keeps growing.
 */
function modeAllowsClickable(mode: StrategyMode, ind: IndicatorMetadata): boolean {
  if (ind.status === "coming_soon") return false;
  if (mode === "beginner") {
    return ind.status === "active" && ind.difficulty === "beginner";
  }
  if (mode === "intermediate") {
    return ind.status === "active";
  }
  // expert
  return ind.status === "active" || ind.status === "experimental";
}

function modeShowsCard(mode: StrategyMode, ind: IndicatorMetadata): boolean {
  // Beginner mode hides experimental noise; intermediate hides
  // experimental too. Expert sees everything. Coming-soon is always
  // visible (greyed) for catalogue discovery.
  if (mode === "beginner" && ind.status === "experimental") return false;
  if (mode === "intermediate" && ind.status === "experimental") return false;
  return true;
}


function useStrategyMode(): StrategyMode {
  const [mode, setMode] = useState<StrategyMode>("beginner");

  useEffect(() => {
    if (typeof window === "undefined") return;
    function read() {
      const stored = window.localStorage.getItem(STRATEGY_MODE_STORAGE_KEY);
      if (stored === "beginner" || stored === "intermediate" || stored === "expert") {
        setMode(stored);
      }
    }
    read();
    // Pick up changes made by other tabs / the dashboard's mode selector.
    function onStorage(event: StorageEvent) {
      if (event.key === STRATEGY_MODE_STORAGE_KEY) read();
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return mode;
}


export function IndicatorLibrary({ indicators }: IndicatorLibraryProps) {
  const mode = useStrategyMode();
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const ind of indicators) set.add(ind.category);
    return Array.from(set).sort();
  }, [indicators]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return indicators.filter((ind) => {
      if (!modeShowsCard(mode, ind)) return false;
      if (activeCategory && ind.category !== activeCategory) return false;
      if (!q) return true;
      const hay =
        `${ind.id} ${ind.name} ${ind.description} ${ind.tags.join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
  }, [indicators, search, activeCategory, mode]);

  function onIndicatorClick(ind: IndicatorMetadata) {
    if (!modeAllowsClickable(mode, ind)) return;
    toast.info(`Add "${ind.name}" to strategy — available in the new builder.`);
  }

  return (
    <div className="space-y-4">
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        categories={categories}
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
      />

      {visible.length === 0 ? (
        <GlassmorphismCard hover={false}>
          <div className="text-center py-10">
            <Search className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
            <h3 className="font-semibold mb-1">No indicators match</h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Try clearing the search or switching category. Switching
              authoring mode at the top of the page reveals more.
            </p>
          </div>
        </GlassmorphismCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map((ind) => (
            <IndicatorCard
              key={ind.id}
              indicator={ind}
              clickable={modeAllowsClickable(mode, ind)}
              onClick={() => onIndicatorClick(ind)}
            />
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Showing {visible.length} of {indicators.length} indicators · mode:{" "}
        <span className="font-medium text-foreground">{mode}</span>
      </p>
    </div>
  );
}


// ─── Filter bar ─────────────────────────────────────────────────────


interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  categories: string[];
  activeCategory: string | null;
  onCategoryChange: (cat: string | null) => void;
}

function FilterBar({
  search,
  onSearchChange,
  categories,
  activeCategory,
  onCategoryChange,
}: FilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="search"
          placeholder="Search by name, id, or tag…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className={cn(
            "w-full rounded-lg pl-9 pr-3 py-2 text-sm",
            "bg-white/[0.02] border border-white/[0.06] text-foreground",
            "placeholder:text-muted-foreground",
            "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
          )}
          aria-label="Search indicators"
        />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <CategoryChip
          label="All"
          active={activeCategory === null}
          onClick={() => onCategoryChange(null)}
        />
        {categories.map((cat) => (
          <CategoryChip
            key={cat}
            label={cat}
            active={activeCategory === cat}
            onClick={() => onCategoryChange(cat === activeCategory ? null : cat)}
          />
        ))}
      </div>
    </div>
  );
}


function CategoryChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "text-xs px-3 py-1 rounded-full border transition-colors",
        active
          ? "bg-accent-blue/15 border-accent-blue/30 text-accent-blue"
          : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:text-foreground hover:bg-white/[0.04]",
      )}
    >
      {label}
    </button>
  );
}


// ─── Indicator card ─────────────────────────────────────────────────


function IndicatorCard({
  indicator,
  clickable,
  onClick,
}: {
  indicator: IndicatorMetadata;
  clickable: boolean;
  onClick: () => void;
}) {
  const isComingSoon = indicator.status === "coming_soon";
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      aria-disabled={!clickable}
      whileHover={clickable ? { y: -2 } : undefined}
      whileTap={clickable ? { scale: 0.99 } : undefined}
      className={cn(
        "text-left rounded-xl p-4 border transition-colors",
        "dark:bg-card/60 dark:backdrop-blur-xl dark:border-border",
        "bg-card border-border shadow-[0_1px_3px_rgba(0,0,0,0.04)]",
        "dark:shadow-none",
        clickable
          ? "hover:border-accent-blue/30 cursor-pointer"
          : "opacity-50 cursor-not-allowed",
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm truncate">{indicator.name}</h3>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">
            {indicator.id}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <StatusBadge status={indicator.status} />
          <IndicatorVerificationBadge slug={indicator.id} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed mb-3">
        {indicator.description}
      </p>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Layers className="h-3 w-3 text-accent-blue" />
          <span className="text-xs text-muted-foreground">
            {indicator.category}
          </span>
        </div>
        <DifficultyBadge difficulty={indicator.difficulty} />
      </div>
      {isComingSoon ? (
        <p className="mt-2 text-[11px] text-muted-foreground italic flex items-center gap-1">
          <Lock className="h-3 w-3" />
          Coming soon — not selectable yet
        </p>
      ) : null}
    </motion.button>
  );
}


function StatusBadge({ status }: { status: IndicatorMetadata["status"] }) {
  if (status === "active") {
    return (
      <Badge className="bg-profit/15 text-profit border-profit/30 gap-1">
        <CheckCircle2 className="h-3 w-3" />
        Active
      </Badge>
    );
  }
  if (status === "experimental") {
    return (
      <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 gap-1">
        <FlaskConical className="h-3 w-3" />
        Experimental
      </Badge>
    );
  }
  return (
    <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.08] gap-1">
      <Lock className="h-3 w-3" />
      Coming soon
    </Badge>
  );
}


function DifficultyBadge({
  difficulty,
}: {
  difficulty: IndicatorMetadata["difficulty"];
}) {
  if (difficulty === "beginner") {
    return (
      <Badge className="bg-white/[0.03] text-muted-foreground border-white/[0.06] gap-1">
        <GraduationCap className="h-3 w-3" />
        Beginner
      </Badge>
    );
  }
  if (difficulty === "intermediate") {
    return (
      <Badge className="bg-white/[0.03] text-muted-foreground border-white/[0.06] gap-1">
        <Sparkles className="h-3 w-3" />
        Intermediate
      </Badge>
    );
  }
  return (
    <Badge className="bg-white/[0.03] text-muted-foreground border-white/[0.06] gap-1">
      <Cpu className="h-3 w-3" />
      Expert
    </Badge>
  );
}
