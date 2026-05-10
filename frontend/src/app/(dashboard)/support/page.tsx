"use client";

/**
 * /support — Help Center landing page.
 *
 * Two tabs (Naya Ticket / Mere Tickets) plus a deep-link to the
 * static FAQ page. Tab state lives in component state — small
 * enough that URL-based persistence isn't worth the
 * SSR / hydration plumbing.
 */

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { BookOpen, HelpCircle, Plus } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { TicketForm } from "@/components/support/ticket-form";
import { MyTicketsList } from "@/components/support/my-tickets-list";
import { cn } from "@/lib/utils";

type Tab = "new" | "mine";

export default function SupportPage() {
  const [tab, setTab] = useState<Tab>("new");
  // Bumping ``refreshKey`` after a successful submit re-mounts the
  // tickets list with a fresh fetch — simpler than threading a
  // refetch callback through the hook.
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-5"
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <HelpCircle className="h-6 w-6 text-accent-blue" />
            Help Center
          </h1>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Koi issue ya question? Pehle FAQ check karo — chances
            hain answer wahan mil jaye. Nahi mile to ticket file
            kar do, hum usually 24-48 ghante mein reply karte hain.
          </p>
        </div>
        <Link href="/support/faq">
          <Button variant="outline" size="sm" type="button">
            <BookOpen className="h-3.5 w-3.5" />
            Browse FAQ
          </Button>
        </Link>
      </header>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-white/[0.04]">
        <TabButton
          active={tab === "new"}
          onClick={() => setTab("new")}
          label="Naya Ticket"
        />
        <TabButton
          active={tab === "mine"}
          onClick={() => setTab("mine")}
          label="Mere Tickets"
        />
      </div>

      {tab === "new" ? (
        <TicketForm
          onSubmitted={() => {
            setRefreshKey((k) => k + 1);
            setTab("mine");
          }}
        />
      ) : (
        <MyTicketsList refreshKey={refreshKey} />
      )}

      {/* Quick FAQ teaser at the bottom */}
      <GlassmorphismCard hover={false}>
        <div className="flex items-start gap-3">
          <BookOpen className="h-4 w-4 text-accent-purple shrink-0 mt-0.5" />
          <div className="space-y-1 flex-1 min-w-0">
            <p className="text-sm font-semibold">Common questions ka jawab</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Strategy kaise banayein, broker connect kaise karein,
              live trading kab enable hota hai — sab kuch FAQ page
              pe likha hai.
            </p>
          </div>
          <Link href="/support/faq">
            <Button variant="outline" size="sm" type="button">
              <Plus className="h-3.5 w-3.5" />
              Read FAQ
            </Button>
          </Link>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
        active
          ? "border-accent-blue text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}
