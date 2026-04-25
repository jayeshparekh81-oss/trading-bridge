"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/hooks/useAlgoMitra";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
          isUser
            ? "bg-accent-blue text-white rounded-br-md"
            : "bg-card border border-border text-foreground rounded-bl-md",
        )}
      >
        {!isUser && (
          <div className="text-[10px] uppercase tracking-wide text-accent-gold font-semibold mb-0.5">
            AlgoMitra
          </div>
        )}
        {message.imageDataUrl && (
          <div className="mb-2 overflow-hidden rounded-lg">
            <Image
              src={message.imageDataUrl}
              alt="User screenshot"
              width={320}
              height={180}
              unoptimized
              className="block max-h-48 w-auto object-cover"
            />
          </div>
        )}
        {message.content && (
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        )}
      </div>
    </motion.div>
  );
}
