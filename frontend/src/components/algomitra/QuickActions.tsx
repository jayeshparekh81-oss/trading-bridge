"use client";

import { motion } from "framer-motion";
import { Phone, MessageCircle, Mail } from "lucide-react";
import type { FlowOption } from "@/lib/algomitra-flows";
import { ALGOMITRA_ESCALATION } from "@/lib/algomitra-personality";

interface QuickActionsProps {
  options?: readonly FlowOption[];
  onSelect: (option: FlowOption) => void;
}

/**
 * Renders the active flow's quick-action chips above the input. When the
 * flow has no options, falls back to the persistent escalation row so
 * users can always reach a human.
 */
export function QuickActions({ options, onSelect }: QuickActionsProps) {
  if (options && options.length > 0) {
    return (
      <div className="flex flex-wrap gap-2 border-t border-border bg-card/40 px-3 py-2.5">
        {options.map((opt, i) => (
          <motion.button
            key={`${opt.label}-${i}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            type="button"
            onClick={() => onSelect(opt)}
            className="inline-flex items-center gap-1.5 rounded-full border border-accent-gold/30 bg-accent-gold/10 px-3 py-1 text-xs font-medium text-foreground hover:bg-accent-gold/20 hover:border-accent-gold/60 transition-colors"
          >
            {opt.emoji && <span aria-hidden>{opt.emoji}</span>}
            <span>{opt.label}</span>
          </motion.button>
        ))}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 border-t border-border bg-card/40 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-1">
        Escalate:
      </span>
      <a
        href={ALGOMITRA_ESCALATION.calendlyUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs hover:border-accent-blue/50 hover:text-accent-blue transition-colors"
      >
        <Phone className="h-3 w-3" />
        Founder
      </a>
      <a
        href={ALGOMITRA_ESCALATION.whatsappUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs hover:border-neon-green/50 hover:text-neon-green transition-colors"
      >
        <MessageCircle className="h-3 w-3" />
        WhatsApp
      </a>
      <a
        href={ALGOMITRA_ESCALATION.emailUrl}
        className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs hover:border-accent-purple/50 hover:text-accent-purple transition-colors"
      >
        <Mail className="h-3 w-3" />
        Email
      </a>
    </div>
  );
}
