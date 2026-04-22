"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { useEffect } from "react";

interface MantraModalProps {
  open: boolean;
  onClose: () => void;
}

const MANTRAS = [
  {
    sanskrit: "\u0913\u0902",
    translit: "Om / Aum",
    title: "The Primordial Sound",
    meaning: "Universe ki pehli vibration. A (creation) \u00b7 U (preservation) \u00b7 M (dissolution) \u00b7 silent 4th beat (eternal witness).",
    connect: "Market ke 3 states \u2014 Bull, Sideways, Bear. Trader = silent observer above it all. Om bindu apex pe = witness consciousness.",
    color: "text-accent-gold",
  },
  {
    sanskrit: "\u0915\u093e\u0932\u091a\u0915\u094d\u0930",
    translit: "Kalachakra",
    title: "The Wheel of Time",
    meaning: "Kaal (time) + Chakra (wheel). Ancient Hindu/Buddhist concept \u2014 time is cyclical, not linear. Seasons, patterns, cycles repeat.",
    connect: "Logo ka 60-mark mandala = literal Kalachakra. History doesn\u2019t repeat but rhymes. Chart patterns timeless. Time wheel keeps turning.",
    color: "text-accent-blue",
  },
  {
    sanskrit: "\u0924\u094d\u0930\u093f\u0915\u093e\u0932",
    translit: "Trikala",
    title: "The Three Times",
    meaning: "Bhoot (Past) \u00b7 Vartamaan (Present) \u00b7 Bhavishya (Future). One who sees all three = Trikaladarshi (seer of times).",
    connect: "Logo ke 3 candles. PAST (saffron) = backtesting 20-year NSE data. PRESENT (white) = live execution. FUTURE (green) = AI prediction.",
    color: "text-profit",
  },
  {
    sanskrit: "\u0924\u094d\u0930\u093f\u0936\u0942\u0932",
    translit: "Trishul",
    title: "Shiva\u2019s Trident",
    meaning: "3 prongs = 3 gunas (Sattva/Rajas/Tamas). Destroyer of illusion. Also on Ashoka Chakra spokes of Indian flag.",
    connect: "Sattva = disciplined trading. Rajas = FOMO/greed. Tamas = panic freezing. Trishul cuts all 3 imbalances. Watermark inside triangle.",
    color: "text-accent-purple",
  },
  {
    sanskrit: "\u0924\u094d\u0930\u093f\u0938\u094d\u0915\u0947\u0932\u093f\u092f\u0928",
    translit: "Triskelion",
    title: "The Three-Dot Cycle",
    meaning: "Ancient 3-dot geometry. Found on 1000 BCE Kuru Janpada coins \u2014 India\u2019s oldest currency. Cycles, motion, progress.",
    connect: "Logo ke 3 corner dots = literal Triskelion. Saffron bottom-left \u00b7 Gold apex (Om) \u00b7 Green bottom-right. 3000 years of trading heritage.",
    color: "text-accent-gold",
  },
];

export function MantrasModal({ open, onClose }: MantraModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-accent-gold/20 bg-background/95 backdrop-blur-xl shadow-2xl shadow-accent-gold/10"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/5 transition-colors z-10"
              aria-label="Close"
            >
              <X className="h-5 w-5 text-muted-foreground" />
            </button>

            <div className="p-8 md:p-10 space-y-8">
              <div className="text-center space-y-3 pb-2">
                <p className="text-[11px] tracking-[0.35em] text-accent-gold/70 font-mono uppercase">
                  The TRADETRI Codex
                </p>
                <h2 className="text-2xl md:text-3xl font-serif font-bold text-foreground">
                  Why five sacred words?
                </h2>
                <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
                  Logo sirf design nahi \u2014 3000 saal ki Indian trading wisdom compressed. Har shabd ka market se gehra connection.
                </p>
              </div>

              <div className="space-y-5">
                {MANTRAS.map((m, i) => (
                  <motion.div
                    key={m.translit}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 + i * 0.08 }}
                    className="border-l-2 border-accent-gold/30 pl-5 py-2 hover:border-accent-gold/60 transition-colors"
                  >
                    <div className="flex items-baseline gap-3 flex-wrap mb-2">
                      <span className={`text-2xl font-serif ${m.color}`}>{m.sanskrit}</span>
                      <span className="text-sm font-mono text-muted-foreground tracking-wider">
                        {m.translit}
                      </span>
                      <span className="text-xs text-muted-foreground/70 italic">\u2014 {m.title}</span>
                    </div>
                    <p className="text-sm text-foreground/90 leading-relaxed mb-2">{m.meaning}</p>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      <span className="text-accent-gold/80 font-medium">Trading connection: </span>
                      {m.connect}
                    </p>
                  </motion.div>
                ))}
              </div>

              <div className="pt-4 border-t border-white/5 text-center">
                <p className="text-[11px] tracking-[0.25em] text-muted-foreground/60 font-mono uppercase">
                  No foreign trading platform can touch this depth.
                </p>
                <p className="text-xs text-accent-gold/70 mt-2 italic">
                  This is TRADETRI\u2019s unfair moat. Made in Bharat. \ud83c\uddee\ud83c\uddf3
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
