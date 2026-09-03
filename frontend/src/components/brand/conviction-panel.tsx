"use client";

import { motion } from "framer-motion";

/**
 * ConvictionPanel — illustrates the ADVISORY conviction score each signal
 * carries. The score informs the decision; it does not replace it.
 *
 * HONESTY, and why this panel is narrower than it used to be:
 *
 * It previously showed a third row scored BELOW the threshold, rendered
 * "REJECTED", and captioned that you can see why a trade was taken "ya chhoda
 * gaya" (or skipped). Both were false in the same way. On the live strategy we
 * actually sell, the validator has REJECTED 0 of 40 signals — 26 of those carry
 * no decision at all. Illustrating a rejection as typical, and promising the
 * user sight of skip-reasons, describes an event that has never occurred.
 *
 * So: only rows that clear the threshold are shown, and the caption claims
 * nothing about skipped trades. Rows remain STATIC sample data, tagged
 * "EXAMPLE", on neutral index futures with no real strategy named.
 */

type Signal = {
  symbol: string;
  score: number; // 0..1
};

const THRESHOLD = 0.6;

//: Only ABOVE-threshold rows. A below-threshold "REJECTED" row illustrated a
//: rejection that has never happened on the strategy we sell (0 of 40).
const SIGNALS: Signal[] = [
  { symbol: "NIFTY-FUT", score: 0.86 },
  { symbol: "BANKNIFTY-FUT", score: 0.72 },
];

export function ConvictionPanel() {
  return (
    <div className="glass rounded-2xl p-4 sm:p-5 space-y-3.5">
      {/* header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-[0.22em] text-accent-gold/80 uppercase">
            AI Conviction
          </span>
          <span className="text-[8px] font-mono tracking-[0.18em] uppercase px-1.5 py-0.5 rounded-full border border-white/20 text-muted-foreground/70">
            Example
          </span>
        </div>
        <span className="text-[9px] font-mono tabular-nums text-muted-foreground/60">
          threshold {THRESHOLD.toFixed(2)}
        </span>
      </div>

      {/* rows */}
      <div className="space-y-3">
        {SIGNALS.map((s, i) => {
          const approved = s.score >= THRESHOLD;
          return (
            <motion.div
              key={s.symbol}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.45, delay: 0.55 + i * 0.12 }}
              className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[11px] text-foreground/90 truncate">
                  {s.symbol}
                </span>
                <span className="font-mono text-[9px] tracking-wider text-muted-foreground/55 uppercase">
                  Entry
                </span>
              </div>

              <div className="flex items-center gap-2 justify-self-end">
                <span
                  className={`font-mono text-[11px] tabular-nums ${approved ? "text-profit" : "text-loss"}`}
                >
                  {s.score.toFixed(2)}
                </span>
                <span
                  className={`font-mono text-[9px] tracking-wider uppercase whitespace-nowrap ${approved ? "text-profit" : "text-loss"}`}
                >
                  {approved ? "Approved ✓" : "Rejected ✕"}
                </span>
              </div>

              {/* score bar — spans both columns; vertical tick marks the threshold */}
              <div className="col-span-2 relative h-1.5 rounded-full bg-white/10 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.round(s.score * 100)}%` }}
                  transition={{
                    duration: 0.7,
                    delay: 0.65 + i * 0.12,
                    ease: "easeOut",
                  }}
                  className={`h-full rounded-full ${
                    approved
                      ? "bg-gradient-to-r from-emerald-500 to-profit"
                      : "bg-loss/70"
                  }`}
                />
                <div
                  className="absolute inset-y-0 w-px bg-white/55"
                  style={{ left: `${THRESHOLD * 100}%` }}
                  aria-hidden="true"
                />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* caption */}
      <p className="text-[10.5px] leading-relaxed text-muted-foreground/80">
        Har signal apne conviction score ke saath dikhta hai — act karne se
        pehle. Ye score advisory hai; aapka decision replace nahi karta.
      </p>
    </div>
  );
}
