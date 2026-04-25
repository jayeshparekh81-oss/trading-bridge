"use client";

import { useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from "react";
import { Image as ImageIcon, Send } from "lucide-react";
import { toast } from "sonner";

interface InputAreaProps {
  disabled?: boolean;
  onSendMessage: (text: string) => void;
  onSendImage: (dataUrl: string, fileName: string) => void;
}

const MAX_IMAGE_BYTES = 4 * 1024 * 1024; // 4 MB

export function InputArea({ disabled, onSendMessage, onSendImage }: InputAreaProps) {
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  function trySend() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSendMessage(trimmed);
    setText("");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    trySend();
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      trySend();
    }
  }

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Sirf images upload kar sakte ho bhai");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error("Image bahut badi hai — 4 MB se kam rakh");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        onSendImage(result, file.name);
      }
    };
    reader.onerror = () => toast.error("Image read nahi ho payi — dobara try kar");
    reader.readAsDataURL(file);
    // Reset input so same file can be re-selected
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 border-t border-border bg-card/80 backdrop-blur px-3 py-2.5"
    >
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFile}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={disabled}
        aria-label="Attach screenshot"
        className="shrink-0 rounded-lg border border-border bg-transparent p-2 text-muted-foreground hover:text-accent-gold hover:border-accent-gold/40 transition-colors disabled:opacity-50"
      >
        <ImageIcon className="h-4 w-4" />
      </button>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        disabled={disabled}
        rows={1}
        placeholder="Bhai, message likh..."
        className="flex-1 min-w-0 resize-none rounded-lg border border-input bg-transparent px-3 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30 max-h-32"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        aria-label="Send message"
        className="shrink-0 rounded-lg bg-accent-gold p-2 text-black hover:brightness-110 transition disabled:opacity-50"
      >
        <Send className="h-4 w-4" />
      </button>
    </form>
  );
}
