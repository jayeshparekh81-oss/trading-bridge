"use client";

import { motion } from "framer-motion";
import { BookOpen, AlertTriangle, RefreshCw } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import {
  IndicatorLibrary,
  type IndicatorMetadata,
} from "@/components/strategies/indicator-library";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};


export default function IndicatorLibraryPage() {
  const { data, isLoading, error, refetch } = useApi<IndicatorMetadata[]>(
    "/strategies/indicators",
    null,
  );

  const indicators = data ?? [];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-accent-blue" />
            Indicator Library
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Browse the catalogue. Mode at the top of /strategies controls
            which indicators are clickable here.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={refetch} type="button">
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          Refresh
        </Button>
      </motion.div>

      {error && !data ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-8">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">
                Could not load indicator library
              </h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <Button variant="outline" size="sm" onClick={refetch} type="button">
                Retry
              </Button>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : isLoading && !data ? (
        <motion.div variants={fadeUp} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <GlassmorphismCard key={i} hover={false}>
              <div className="animate-pulse space-y-3">
                <div className="h-4 w-2/3 bg-white/[0.05] rounded" />
                <div className="h-3 w-1/3 bg-white/[0.04] rounded" />
                <div className="h-3 w-full bg-white/[0.03] rounded" />
                <div className="h-3 w-3/4 bg-white/[0.03] rounded" />
              </div>
            </GlassmorphismCard>
          ))}
        </motion.div>
      ) : (
        <motion.div variants={fadeUp}>
          <IndicatorLibrary indicators={indicators} />
        </motion.div>
      )}
    </motion.div>
  );
}
