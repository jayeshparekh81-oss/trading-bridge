"use client";

import { X, RotateCcw } from "lucide-react";
import { ALGOMITRA_PROFILE } from "@/lib/algomitra-personality";

interface ChatHeaderProps {
  onClose: () => void;
  onReset: () => void;
}

export function ChatHeader({ onClose, onReset }: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-card/80 backdrop-blur px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <div className="relative shrink-0">
          <div className="h-9 w-9 rounded-full bg-gradient-to-br from-accent-gold to-accent-purple flex items-center justify-center text-base font-bold text-white">
            AM
          </div>
          <span
            className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-neon-green ring-2 ring-card"
            aria-label="Online"
          />
        </div>
        <div className="min-w-0">
          <div className="font-heading text-sm font-semibold leading-none">
            {ALGOMITRA_PROFILE.name}
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
            {ALGOMITRA_PROFILE.shortTag}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onReset}
          aria-label="Restart conversation"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
