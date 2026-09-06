/**
 * Strategy explainer content type — bilingual, plain-language complement
 * to the JSON `config_json` shipped with each active equity template
 * in `backend/data/strategy_templates_seed.json`.
 *
 * Where the seed JSON answers "what does this strategy DO mechanically",
 * the explainer answers:
 *   - What is the *idea* a beginner needs to grasp?
 *   - When does this setup work (and when not)?
 *   - What mistakes do new traders make running it?
 *   - What's a realistic return expectation, honestly?
 *   - What's a concrete example trade on a known NSE/F&O symbol?
 *
 * Voice rules:
 *   - English: clear, jargon-defined, no hype.
 *   - Hindi: Hinglish (conversational), not formal Devanagari.
 *   - Numbers honest, not pumped. Win rates, drawdowns, returns must
 *     be plausible for retail F&O reality (most strategies = 50-60%
 *     win rate, 10-25% annual paper-mode return at sensible sizing,
 *     not 200% / 90% / get-rich curves).
 */

export interface ExampleTrade {
  /** Indian symbol — NIFTY, BANKNIFTY, RELIANCE, HDFCBANK, etc. */
  symbol: string;
  /** Entry context: trigger that fired the entry. */
  entry: string;
  /** Exit context: which exit rule closed the trade. */
  exit: string;
  /** Net result in ₹ (paper-mode realistic). */
  pnl: string;
}

export interface StrategyExplainer {
  /** Matches the slug in `backend/data/strategy_templates_seed.json`. */
  slug: string;

  /** 2-paragraph layman explanation in English. */
  what_it_does: string;
  /** 2-paragraph layman explanation in Hinglish. */
  what_it_does_hi: string;

  /** When the strategy has edge — market regime / conditions. */
  best_market_conditions: string;
  /** When the strategy struggles — avoid these conditions. */
  worst_market_conditions: string;

  /** Three plain-language mistakes new traders make running this. */
  common_mistakes: [string, string, string];

  /** Honest expectations — win rate, typical R:R, monthly bands. */
  realistic_returns: string;

  /** Single concrete example trade on a real Indian symbol. */
  example_trade: ExampleTrade;

  /** Slugs of strategies to graduate to once this one is mastered. */
  follow_up_strategies: string[];

  /** Subjective 1 (easy) - 5 (hard) difficulty rating. */
  difficulty_score: 1 | 2 | 3 | 4 | 5;

  /** Subjective 1 (low) - 5 (high) capital efficiency rating —
   *  how much capital does this strategy lock up vs return generated. */
  capital_efficiency_score: 1 | 2 | 3 | 4 | 5;
}
