"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAlgoMitra } from "@/hooks/useAlgoMitra";
import { ChatHeader } from "./ChatHeader";
import { MessageBubble } from "./MessageBubble";
import { InputArea } from "./InputArea";
import { QuickActions } from "./QuickActions";

export function ChatWidget() {
  const {
    isOpen,
    open,
    close,
    reset,
    unreadCount,
    messages,
    activeOptions,
    isThinking,
    sendUserText,
    sendUserImage,
    selectOption,
  } = useAlgoMitra();

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isOpen, isThinking]);

  return (
    <>
      {/* Floating launcher */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            key="launcher"
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 20 }}
            transition={{ duration: 0.2 }}
            onClick={open}
            type="button"
            aria-label="Open AlgoMitra chat"
            className="fixed bottom-20 right-4 md:bottom-6 md:right-6 z-40 group flex items-center gap-2 rounded-full bg-gradient-to-br from-accent-gold to-accent-purple px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-accent-gold/20 hover:shadow-accent-gold/40 transition-shadow"
          >
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-green opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-neon-green" />
            </span>
            <MessageCircle className="h-4 w-4" />
            <span className="hidden sm:inline">AlgoMitra</span>
            {unreadCount > 0 && (
              <span
                aria-label={`${unreadCount} unread`}
                className="ml-1 inline-flex min-w-5 items-center justify-center rounded-full bg-loss px-1.5 text-[10px] font-bold text-white"
              >
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </motion.button>
        )}
      </AnimatePresence>

      {/* Slide-in panel */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={close}
              className="fixed inset-0 z-40 bg-black/30 supports-backdrop-filter:backdrop-blur-sm md:hidden"
            />
            <motion.div
              key="panel"
              initial={{ opacity: 0, x: 24, y: 24 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: 24, y: 24 }}
              transition={{ duration: 0.2 }}
              role="dialog"
              aria-label="AlgoMitra chat"
              className={cn(
                "fixed z-50 flex flex-col bg-popover ring-1 ring-foreground/10",
                // Mobile: full-screen sheet from bottom
                "inset-x-2 bottom-2 top-12 rounded-2xl",
                // Desktop: floating panel pinned bottom-right
                "md:inset-auto md:bottom-6 md:right-6 md:top-auto md:left-auto md:h-[600px] md:max-h-[80vh] md:w-[400px] md:rounded-2xl",
              )}
            >
              <ChatHeader onClose={close} onReset={reset} />
              <div
                ref={scrollRef}
                className="flex-1 space-y-3 overflow-y-auto bg-background/50 px-3 py-3"
              >
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={m} />
                ))}
                {isThinking && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15 }}
                    className="flex w-full justify-start"
                    aria-live="polite"
                  >
                    <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-border bg-card px-3.5 py-2 text-sm leading-relaxed">
                      <div className="text-[10px] uppercase tracking-wide text-accent-gold font-semibold mb-0.5">
                        AlgoMitra
                      </div>
                      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                        soch raha hai
                        <span className="inline-flex gap-0.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
                          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
                          <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" />
                        </span>
                        <span aria-hidden>🤔</span>
                      </span>
                    </div>
                  </motion.div>
                )}
              </div>
              <QuickActions options={activeOptions} onSelect={selectOption} />
              <InputArea
                onSendMessage={sendUserText}
                onSendImage={sendUserImage}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
