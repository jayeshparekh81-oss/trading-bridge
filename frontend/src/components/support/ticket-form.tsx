"use client";

/**
 * Ticket-creation form. Reads the 6 categories from a local
 * constant table that mirrors the backend's enum exactly — if a
 * future category lands, both ends update in lockstep.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Send } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Category =
  | "bug"
  | "billing"
  | "broker_connection"
  | "strategy_help"
  | "account"
  | "other";

interface CategoryOption {
  value: Category;
  label: string;
  hint: string;
}

const CATEGORIES: ReadonlyArray<CategoryOption> = [
  { value: "strategy_help", label: "Strategy Help", hint: "Builder ya backtest mein madad chahiye" },
  { value: "broker_connection", label: "Broker Connection", hint: "Broker connect / disconnect / reconnect issues" },
  { value: "bug", label: "Bug Report", hint: "Kuch toot raha hai ya unexpected behaviour" },
  { value: "billing", label: "Billing", hint: "Subscription, payment, refund queries" },
  { value: "account", label: "Account", hint: "Login, password, profile, settings" },
  { value: "other", label: "Other", hint: "Upar list mein nahi hai? Yahan likho" },
];

interface TicketFormProps {
  onSubmitted: () => void;
}

export function TicketForm({ onSubmitted }: TicketFormProps) {
  const [category, setCategory] = useState<Category>("strategy_help");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit =
    subject.trim().length > 0 &&
    description.trim().length > 0 &&
    !submitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await api.post("/support/tickets", {
        category,
        subject: subject.trim(),
        description: description.trim(),
      });
      toast.success("🎉 Ticket submit ho gaya — admin team jaldi reply karegi");
      setSubject("");
      setDescription("");
      onSubmitted();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Ticket submit nahi ho paya — refresh karke try karo";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <header className="space-y-1">
          <h3 className="text-sm font-semibold">Naya Ticket Banao</h3>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Description thoda detailed likho — error messages, kya
            try kiya, kab problem hui. Jitni clear info, utna
            jaldi help milegi.
          </p>
        </header>

        {/* Category picker */}
        <div className="space-y-1.5">
          <label className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Category
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {CATEGORIES.map((cat) => (
              <CategoryButton
                key={cat.value}
                option={cat}
                active={category === cat.value}
                onSelect={() => setCategory(cat.value)}
              />
            ))}
          </div>
        </div>

        {/* Subject */}
        <div className="space-y-1.5">
          <label
            htmlFor="ticket-subject"
            className="text-[10px] uppercase tracking-wide text-muted-foreground"
          >
            Subject *
          </label>
          <Input
            id="ticket-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Ek line mein issue summarize karo"
            maxLength={200}
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label
            htmlFor="ticket-description"
            className="text-[10px] uppercase tracking-wide text-muted-foreground"
          >
            Description *
          </label>
          <textarea
            id="ticket-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Detail mein likho — error messages, kya try kiya, screenshot link..."
            maxLength={5000}
            rows={6}
            className={cn(
              "w-full rounded-md px-3 py-2 text-sm",
              "bg-white/[0.02] border border-white/[0.06] text-foreground",
              "placeholder:text-muted-foreground",
              "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
              "resize-y",
            )}
          />
          <p className="text-[10px] text-muted-foreground/70 text-right">
            {description.length} / 5000
          </p>
        </div>

        <motion.div whileTap={{ scale: 0.99 }} className="flex justify-end">
          <GlowButton
            size="sm"
            onClick={handleSubmit}
            disabled={!canSubmit}
            type="button"
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            Submit Ticket
          </GlowButton>
        </motion.div>
      </div>
    </GlassmorphismCard>
  );
}

function CategoryButton({
  option,
  active,
  onSelect,
}: {
  option: CategoryOption;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "rounded-lg border p-2.5 text-left transition-colors",
        active
          ? "bg-accent-blue/[0.08] border-accent-blue/40"
          : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold">{option.label}</span>
        {active ? (
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[9px] uppercase">
            Selected
          </Badge>
        ) : null}
      </div>
      <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
        {option.hint}
      </p>
    </button>
  );
}
