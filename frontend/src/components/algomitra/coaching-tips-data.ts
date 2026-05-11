/**
 * Static coaching tips for the Always-On AlgoMitra panel.
 *
 * Phase 1 shipped Hinglish only. This iteration adds four more
 * languages (Hindi / Gujarati / Tamil / Bengali) — the highest-
 * priority Indian-market languages outside Hinglish. v1.1 batch
 * (deferred): Marathi / Telugu / Kannada / Malayalam / Punjabi /
 * Odia.
 *
 * Schema:
 *
 *   COACHING_TIPS[language][mode][section] = { title, tips: string[] }
 *   WELCOME_MESSAGES[language][mode]       = string
 *
 * Tip-writing rules:
 *
 *   * One sentence per tip, ≤ 90 chars (longer for non-Latin scripts
 *     because each grapheme renders wider — soft cap, not enforced).
 *   * 3 tips per section.
 *   * Technical terms (RSI / EMA / MACD / Stop Loss / NIFTY etc.)
 *     stay in English across every language — Indian financial
 *     vocabulary is bilingual and that's how traders actually read
 *     it.
 *   * Hinglish stays the canonical voice the existing ChatWidget
 *     already uses; the other languages translate that voice into
 *     their script while keeping the same friendly-helpful tone.
 *   * Translations were drafted by Claude; native-speaker review
 *     before v1.1 ship is the open follow-up flagged in the
 *     commit message.
 */

export type BuilderMode = "beginner" | "intermediate" | "expert";

export type BuilderSection =
  | "indicators"
  | "entry"
  | "exit"
  | "risk"
  | "robustness"
  | "json";

export type Language =
  | "hinglish"
  | "english"
  | "hindi"
  | "gujarati"
  | "tamil"
  | "bengali";

export interface CoachingSection {
  title: string;
  tips: string[];
}

export type CoachingTipsForMode = Partial<Record<BuilderSection, CoachingSection>>;

export const DEFAULT_LANGUAGE: Language = "hinglish";

/** Native-script labels for the language switcher dropdown. */
export const LANGUAGE_LABELS: Record<Language, string> = {
  hinglish: "Hinglish",
  english: "English",
  hindi: "हिंदी",
  gujarati: "ગુજરાતી",
  tamil: "தமிழ்",
  bengali: "বাংলা",
};

/** Stable iteration order for the switcher UI. English sits second
 *  (right after Hinglish, the default) so the two most-common
 *  audience picks lead the dropdown. */
export const LANGUAGES: ReadonlyArray<Language> = [
  "hinglish",
  "english",
  "hindi",
  "gujarati",
  "tamil",
  "bengali",
];


// ─── Hinglish (canonical, unchanged from Phase 1) ─────────────────────


const HINGLISH_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "Indicators Kya Hain?",
      tips: [
        "Indicators charts ke patterns dikhate hain — jaise EMA trend dikhata hai.",
        "Beginner ke liye 1-2 indicators kaafi hain — zyada confusion karte hain.",
        "Popular: RSI (overbought/oversold), EMA (trend), MACD (momentum).",
      ],
    },
    entry: {
      title: "Entry Conditions",
      tips: [
        "Entry condition decide karta hai trade kab open ho.",
        "Simple: 'EMA 20 cross EMA 50' = trend change signal.",
        "Beginner: 1-2 conditions chahiye, AND logic se simple rakho.",
      ],
    },
    exit: {
      title: "Exit Strategy",
      tips: [
        "Exit decide karta hai profit/loss kab book ho.",
        "Stop Loss: maximum loss tolerate kar sakte ho.",
        "Target: profit kab book karna — greedy mat bano.",
      ],
    },
    risk: {
      title: "Risk Management",
      tips: [
        "Position size capital ka 2–5 % se zyada nahi.",
        "Stop Loss hamesha mandatory hai — bina nahi trade karo.",
        "Daily loss limit set karo — apne aap ko bachao.",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "Indicators Combine Karna",
      tips: [
        "2–4 indicators ka mix sweet spot hai — over-fitting avoid hota hai.",
        "Trend (EMA / MACD) + momentum (RSI) ka combo strong base hai.",
        "Same family ke indicators (RSI + Stochastic) avoid karo — redundant hain.",
      ],
    },
    entry: {
      title: "Multi-Condition Entries",
      tips: [
        "AND logic strict hai — sab conditions match honi chahiye.",
        "OR logic relaxed — koi ek match ho jaaye toh trade.",
        "Confirmation indicators (volume, ADX) entry ko strong banaate hain.",
      ],
    },
    exit: {
      title: "Smart Exits",
      tips: [
        "Trailing stop loss profit lock karta hai jaise price upar jaata hai.",
        "Partial exit: half qty target pe close, baaki trail karo.",
        "Time-based exit: intraday strategy 15:15 IST tak square off karo.",
      ],
    },
    risk: {
      title: "Position Sizing & Risk",
      tips: [
        "Lot size strategy + capital + stop-loss distance se decide hota hai.",
        "Per-trade risk: capital ka 1 % se 2 % maximum.",
        "Max trades/day cap karo — over-trading mein loss aata hai.",
      ],
    },
  },
  expert: {
    indicators: {
      title: "Advanced Indicator Tuning",
      tips: [
        "Indicator periods ko sensitivity-test karo — robust values pick karo.",
        "Custom params experiment-kar sakte ho, par walk-forward ke saath validate karo.",
        "Experimental indicators (Donchian, ATR-based) Robustness tab ke baad use karo.",
      ],
    },
    entry: {
      title: "Complex Entry Logic",
      tips: [
        "Indicator + candle + price + time conditions sab combine kar sakte ho.",
        "AND/OR top-level operator — nested grouping ke liye JSON tab use karo.",
        "Reverse-signal entry: same condition opposite side trigger karta hai.",
      ],
    },
    exit: {
      title: "Multi-Stage Exits",
      tips: [
        "Partial exits + trailing + indicator-driven exits ek saath use kar sakte ho.",
        "Square-off time intraday strategies ke liye must hai.",
        "Reverse-signal exit position flip karta hai — directional strategies ke liye.",
      ],
    },
    risk: {
      title: "Risk Caps & Override",
      tips: [
        "Daily loss + max trades + capital-per-trade — three lines of defence.",
        "Max loss streak strategy auto-pause trigger karta hai.",
        "Robustness toggle on karo — sensitivity sweep extra confidence deta hai.",
      ],
    },
    robustness: {
      title: "Walk-Forward + Sensitivity",
      tips: [
        "Walk-forward 5 alag time windows mein test karta hai — out-of-sample check.",
        "Sensitivity ±10 % parameter perturbation se overfitting detect karta hai.",
        "Dono enable karna ideal — slow but high-confidence verdict deta hai.",
      ],
    },
    json: {
      title: "Raw JSON Editing",
      tips: [
        "JSON tab read+write — Apply ke baad builder state overwrite ho jaata hai.",
        "Validate-on-blur catches schema errors before submission.",
        "Sync button text ko builder state se refresh karta hai — manual edits ke baad.",
      ],
    },
  },
};


// ─── English (pure English, no Hinglish loanwords) ───────────────────
//
// Tone: warm, supportive, expert — mentor-style. Mirrors the section
// coverage of HINGLISH_TIPS so a user switching language sees the
// same number of cards in the same order. Tips are intentionally
// short (one-liners), matching the existing voice and the 100-150
// word budget the LLM operates on.


const ENGLISH_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "What are indicators?",
      tips: [
        "Indicators reveal patterns in price action — EMA, for instance, smooths price into a trend line.",
        "For beginners, 1–2 indicators are plenty. Adding more usually creates conflicting signals.",
        "Popular picks: RSI (overbought / oversold), EMA (trend direction), MACD (momentum).",
      ],
    },
    entry: {
      title: "Entry conditions",
      tips: [
        "Your entry condition is the rule that opens a trade — keep it specific and testable.",
        "Simple example: 'EMA 20 crosses above EMA 50' marks a trend change.",
        "Stick to 1–2 conditions joined by AND. Fewer rules, cleaner backtest.",
      ],
    },
    exit: {
      title: "Exit strategy",
      tips: [
        "Your exit decides when profit or loss is realised — just as important as the entry.",
        "Stop Loss caps the maximum loss you accept. Always set one.",
        "Target locks in profit. Greed is the most common reason traders give back gains.",
      ],
    },
    risk: {
      title: "Risk management",
      tips: [
        "Risk no more than 2–5 % of capital on any single trade.",
        "Stop Loss is non-negotiable — never enter without one.",
        "Set a daily loss limit and walk away when you hit it. Protect tomorrow.",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "Combining indicators",
      tips: [
        "2–4 indicators is the sweet spot — enough signal, low overfitting risk.",
        "Trend (EMA / MACD) plus momentum (RSI) is a strong base pair.",
        "Avoid same-family indicators (RSI + Stochastic) — they're redundant.",
      ],
    },
    entry: {
      title: "Multi-condition entries",
      tips: [
        "AND is strict: every condition must match for the trade to fire.",
        "OR is relaxed: any one match triggers the trade — useful for confluence.",
        "Confirmation indicators (volume, ADX) strengthen weak entry signals.",
      ],
    },
    exit: {
      title: "Smart exits",
      tips: [
        "A trailing stop locks in profit as price moves in your favour.",
        "Partial exits: close half at target, trail the rest for upside.",
        "Time-based exit: square off intraday positions by 15:15 IST.",
      ],
    },
    risk: {
      title: "Position sizing & risk",
      tips: [
        "Lot size follows from strategy, capital, and stop-loss distance — derive it, don't guess.",
        "Per-trade risk: 1–2 % of capital, no more.",
        "Cap max trades per day. Over-trading is where edge bleeds out.",
      ],
    },
  },
  expert: {
    indicators: {
      title: "Advanced indicator tuning",
      tips: [
        "Sensitivity-test your indicator periods — pick values that stay robust under perturbation.",
        "Experiment with custom params, but validate every change with walk-forward.",
        "Use experimental indicators (Donchian, ATR-based) only after a Robustness tab pass.",
      ],
    },
    entry: {
      title: "Complex entry logic",
      tips: [
        "Combine indicator + candle + price + time conditions for richer signals.",
        "Top-level AND / OR only — use the JSON tab for nested grouping.",
        "Reverse-signal entry fires the same rule on the opposite side — handy for two-way systems.",
      ],
    },
    exit: {
      title: "Multi-stage exits",
      tips: [
        "Stack partial exits, trailing stop, and indicator-driven exits together for layered risk control.",
        "Square-off time is mandatory for any intraday strategy.",
        "Reverse-signal exit flips the position — useful for directional, always-in systems.",
      ],
    },
    risk: {
      title: "Risk caps & overrides",
      tips: [
        "Daily loss, max trades, capital-per-trade — three independent lines of defence.",
        "Max loss streak triggers an automatic strategy pause.",
        "Turn on the robustness toggle — sensitivity sweeps add confidence before going live.",
      ],
    },
    robustness: {
      title: "Walk-forward + sensitivity",
      tips: [
        "Walk-forward tests across 5 distinct windows — an out-of-sample sanity check.",
        "Sensitivity perturbs parameters by ±10 % to surface overfit edges.",
        "Enable both for the strongest verdict — slower runs, much higher confidence.",
      ],
    },
    json: {
      title: "Raw JSON editing",
      tips: [
        "The JSON tab is read+write — Apply overwrites the builder state from the editor.",
        "Validate-on-blur catches schema errors before submission.",
        "Sync refreshes the editor text from the current builder state after manual edits.",
      ],
    },
  },
};


// ─── हिंदी (Hindi, Devanagari) ──────────────────────────────────────


const HINDI_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "इंडिकेटर क्या हैं?",
      tips: [
        "इंडिकेटर चार्ट के पैटर्न दिखाते हैं — जैसे EMA ट्रेंड बताता है।",
        "शुरुआत में 1-2 इंडिकेटर काफ़ी हैं — ज़्यादा से कन्फ्यूज़न बढ़ती है।",
        "लोकप्रिय: RSI (ओवरबॉट/ओवरसोल्ड), EMA (ट्रेंड), MACD (मोमेंटम)।",
      ],
    },
    entry: {
      title: "एंट्री कंडीशन",
      tips: [
        "एंट्री कंडीशन तय करती है कि ट्रेड कब खुलेगा।",
        "सरल नियम: 'EMA 20 cross EMA 50' = ट्रेंड बदलने का संकेत।",
        "शुरुआती लोग 1-2 कंडीशन रखें, AND लॉजिक से सरल रखें।",
      ],
    },
    exit: {
      title: "एग्जिट रणनीति",
      tips: [
        "एग्जिट तय करता है कि प्रॉफिट या लॉस कब बुक हो।",
        "Stop Loss: अधिकतम कितना नुकसान सहन कर सकते हो।",
        "टारगेट: मुनाफा कब बुक करना है — लालच मत करो।",
      ],
    },
    risk: {
      title: "रिस्क मैनेजमेंट",
      tips: [
        "पोज़ीशन साइज़ कैपिटल का 2–5% से ज़्यादा कभी नहीं।",
        "Stop Loss हमेशा अनिवार्य है — इसके बिना ट्रेड न करें।",
        "दैनिक लॉस लिमिट सेट करें — अपनी पूँजी की रक्षा करें।",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "इंडिकेटर मिलाकर इस्तेमाल",
      tips: [
        "2–4 इंडिकेटर का मिक्स बेस्ट है — ओवर-फ़िटिंग से बचाव।",
        "ट्रेंड (EMA / MACD) + मोमेंटम (RSI) का कॉम्बो मज़बूत आधार है।",
        "एक ही फ़ैमिली के इंडिकेटर (RSI + Stochastic) मत मिलाओ — डुप्लिकेट हैं।",
      ],
    },
    entry: {
      title: "मल्टी-कंडीशन एंट्री",
      tips: [
        "AND लॉजिक सख़्त है — सारी कंडीशन साथ मैच होनी चाहिए।",
        "OR लॉजिक उदार — कोई एक मैच हो जाए तो भी ट्रेड हो जाता है।",
        "Confirmation इंडिकेटर (volume, ADX) एंट्री को मज़बूत बनाते हैं।",
      ],
    },
    exit: {
      title: "स्मार्ट एग्जिट",
      tips: [
        "Trailing Stop Loss प्रॉफ़िट लॉक करता है जैसे ही प्राइस ऊपर जाता है।",
        "Partial Exit: आधी क्वांटिटी टारगेट पर बेचो, बाक़ी ट्रेल करो।",
        "टाइम-बेस्ड एग्जिट: इंट्राडे को 15:15 IST तक स्क्वायर ऑफ़ करें।",
      ],
    },
    risk: {
      title: "पोज़ीशन साइज़ + रिस्क",
      tips: [
        "लॉट साइज़ रणनीति + कैपिटल + Stop Loss दूरी से तय होता है।",
        "प्रति-ट्रेड रिस्क: कैपिटल का 1% से 2% तक ही।",
        "Max Trades/Day सीमा रखो — ओवर-ट्रेडिंग से नुकसान होता है।",
      ],
    },
  },
  expert: {
    indicators: {
      title: "एडवांस्ड इंडिकेटर ट्यूनिंग",
      tips: [
        "Indicator periods की sensitivity-test करें — मज़बूत वैल्यू चुनें।",
        "Custom params एक्सपेरिमेंट करो, पर walk-forward से वैलिडेट करो।",
        "Experimental इंडिकेटर (Donchian, ATR) Robustness टैब के बाद ही उपयोग।",
      ],
    },
    entry: {
      title: "जटिल एंट्री लॉजिक",
      tips: [
        "Indicator + candle + price + time कंडीशन एक साथ मिला सकते हो।",
        "AND/OR टॉप-लेवल operator — nested grouping के लिए JSON टैब उपयोग।",
        "Reverse-signal एंट्री: वही condition विपरीत दिशा में ट्रिगर करती है।",
      ],
    },
    exit: {
      title: "मल्टी-स्टेज एग्जिट",
      tips: [
        "Partial + trailing + indicator-driven एग्जिट सब एक साथ चला सकते हो।",
        "इंट्राडे रणनीतियों के लिए Square-off time अनिवार्य है।",
        "Reverse-signal एग्जिट पोज़ीशन flip करता है — directional strategies के लिए।",
      ],
    },
    risk: {
      title: "रिस्क सीमाएँ + ओवरराइड",
      tips: [
        "Daily loss + max trades + capital-per-trade — तीन सुरक्षा परतें।",
        "Max loss streak रणनीति को auto-pause trigger करती है।",
        "Robustness toggle ऑन रखो — sensitivity sweep से extra भरोसा।",
      ],
    },
    robustness: {
      title: "वॉक-फ़ॉरवर्ड + सेन्सिटिविटी",
      tips: [
        "Walk-forward 5 अलग समय windows पर टेस्ट करता है — out-of-sample check।",
        "Sensitivity ±10% parameter perturbation से over-fitting पकड़ता है।",
        "दोनों enable रखना ideal — धीमा पर भरोसेमंद verdict मिलता है।",
      ],
    },
    json: {
      title: "रॉ JSON एडिटिंग",
      tips: [
        "JSON टैब पढ़ने+लिखने का — Apply के बाद बिल्डर state overwrite होता है।",
        "Validate-on-blur स्कीमा एरर सबमिट से पहले पकड़ लेता है।",
        "Sync बटन manual edits के बाद टेक्स्ट को बिल्डर state से refresh करता है।",
      ],
    },
  },
};


// ─── ગુજરાતી (Gujarati) ────────────────────────────────────────────


const GUJARATI_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "ઇન્ડિકેટર શું છે?",
      tips: [
        "ઇન્ડિકેટર ચાર્ટના પૅટર્ન બતાવે છે — જેમ કે EMA ટ્રેન્ડ બતાવે છે.",
        "શરૂઆતમાં 1-2 ઇન્ડિકેટર પૂરતા છે — વધારે મૂંઝવણ ઉભી કરે છે.",
        "પ્રખ્યાત: RSI (ઓવરબોટ/ઓવરસોલ્ડ), EMA (ટ્રેન્ડ), MACD (મોમેન્ટમ).",
      ],
    },
    entry: {
      title: "એન્ટ્રી શરત",
      tips: [
        "એન્ટ્રી શરત નક્કી કરે છે કે ટ્રેડ ક્યારે ખુલે.",
        "સરળ: 'EMA 20 cross EMA 50' = ટ્રેન્ડ બદલવાનો સંકેત.",
        "બિગિનર: 1-2 શરત રાખો, AND લોજિક સાથે સરળ રાખો.",
      ],
    },
    exit: {
      title: "એક્ઝિટ વ્યૂહરચના",
      tips: [
        "એક્ઝિટ નક્કી કરે છે કે પ્રોફિટ/લોસ ક્યારે બૂક થાય.",
        "Stop Loss: કેટલું નુકસાન સહન કરી શકો.",
        "ટાર્ગેટ: નફો ક્યારે બૂક કરવો — લોભ ન કરો.",
      ],
    },
    risk: {
      title: "રિસ્ક મેનેજમેન્ટ",
      tips: [
        "પોઝિશન સાઇઝ મૂડીના 2–5%થી વધારે ક્યારેય નહીં.",
        "Stop Loss હંમેશા ફરજિયાત છે — તેના વગર ટ્રેડ ન કરો.",
        "દૈનિક લોસ લિમિટ સેટ કરો — પોતાની મૂડી બચાવો.",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "ઇન્ડિકેટર સંયોજન",
      tips: [
        "2–4 ઇન્ડિકેટરનું મિશ્રણ બેસ્ટ છે — over-fitting થી બચાવ.",
        "ટ્રેન્ડ (EMA / MACD) + મોમેન્ટમ (RSI) મજબૂત આધાર છે.",
        "એક જ ફેમિલીના ઇન્ડિકેટર (RSI + Stochastic) ભેગા ન કરો.",
      ],
    },
    entry: {
      title: "મલ્ટી-કન્ડિશન એન્ટ્રી",
      tips: [
        "AND લોજિક કડક છે — બધી શરત મેચ થવી જોઈએ.",
        "OR લોજિક છૂટ આપે છે — એક પણ મેચ થાય તો ટ્રેડ થાય.",
        "Confirmation ઇન્ડિકેટર (volume, ADX) એન્ટ્રી ને મજબૂત બનાવે.",
      ],
    },
    exit: {
      title: "સ્માર્ટ એક્ઝિટ",
      tips: [
        "Trailing Stop Loss પ્રોફિટ લોક કરે છે જેમ પ્રાઇસ ઉપર જાય.",
        "Partial Exit: અડધી ક્વોન્ટિટી ટાર્ગેટ પર બંધ, બાકી ટ્રેલ કરો.",
        "ટાઇમ-આધારિત એક્ઝિટ: ઇન્ટ્રાડે 15:15 IST સુધી square off.",
      ],
    },
    risk: {
      title: "પોઝિશન સાઇઝ + રિસ્ક",
      tips: [
        "લોટ સાઇઝ વ્યૂહરચના + મૂડી + Stop Loss અંતરથી નક્કી થાય.",
        "પ્રતિ-ટ્રેડ રિસ્ક: મૂડીના 1% થી 2% સુધી જ.",
        "Max Trades/Day મર્યાદા રાખો — over-trading માં નુકસાન.",
      ],
    },
  },
  expert: {
    indicators: {
      title: "એડવાન્સ્ડ ઇન્ડિકેટર ટ્યુનિંગ",
      tips: [
        "Indicator periods ની sensitivity-test કરો — મજબૂત મૂલ્ય પસંદ કરો.",
        "Custom params સાથે પ્રયોગ કરો, પણ walk-forward થી validate કરો.",
        "Experimental ઇન્ડિકેટર (Donchian, ATR) Robustness પછી જ વાપરો.",
      ],
    },
    entry: {
      title: "જટિલ એન્ટ્રી લોજિક",
      tips: [
        "Indicator + candle + price + time શરત એક સાથે ગોઠવી શકો.",
        "AND/OR top-level operator — nested grouping માટે JSON tab.",
        "Reverse-signal એન્ટ્રી: એ જ શરત વિરુદ્ધ બાજુ trigger કરે છે.",
      ],
    },
    exit: {
      title: "મલ્ટી-સ્ટેજ એક્ઝિટ",
      tips: [
        "Partial + trailing + indicator-driven એક્ઝિટ સાથે વાપરી શકો.",
        "Square-off time ઇન્ટ્રાડે માટે ફરજિયાત છે.",
        "Reverse-signal એક્ઝિટ પોઝિશન flip કરે છે — directional strategy માટે.",
      ],
    },
    risk: {
      title: "રિસ્ક સીમા + ઓવરરાઇડ",
      tips: [
        "Daily loss + max trades + capital-per-trade — ત્રણ સુરક્ષાસ્તર.",
        "Max loss streak strategy ને auto-pause trigger કરે છે.",
        "Robustness toggle ઓન રાખો — sensitivity sweep વધારે ભરોસો આપે.",
      ],
    },
    robustness: {
      title: "વૉક-ફૉરવર્ડ + સેન્સિટિવિટી",
      tips: [
        "Walk-forward 5 અલગ ટાઇમ વિન્ડોમાં test કરે — out-of-sample check.",
        "Sensitivity ±10% parameter perturbation થી over-fitting પકડાય.",
        "બંને enable રાખવા ideal — ધીમું પણ ભરોસાપાત્ર verdict.",
      ],
    },
    json: {
      title: "Raw JSON એડિટિંગ",
      tips: [
        "JSON tab read+write — Apply પછી builder state overwrite થાય.",
        "Validate-on-blur સ્કીમા એરર submission પહેલા પકડી લે છે.",
        "Sync button text ને builder state થી refresh કરે — manual edits પછી.",
      ],
    },
  },
};


// ─── தமிழ் (Tamil) ──────────────────────────────────────────────────


const TAMIL_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "இண்டிகேட்டர் என்றால் என்ன?",
      tips: [
        "இண்டிகேட்டர் சார்ட்டின் பேட்டர்னை காட்டும் — EMA போக்கை காட்டும்.",
        "ஆரம்பநிலையில் 1-2 இண்டிகேட்டர் போதும் — அதிகமானால் குழப்பம்.",
        "பிரபலம்: RSI (overbought/oversold), EMA (போக்கு), MACD (மொமென்டம்).",
      ],
    },
    entry: {
      title: "நுழைவு நிபந்தனை",
      tips: [
        "நுழைவு நிபந்தனை ட்ரேட் எப்போது திறக்கும் என்று முடிவு செய்யும்.",
        "எளிய: 'EMA 20 cross EMA 50' = போக்கு மாற்றத்தின் சமிக்ஞை.",
        "ஆரம்பநிலை: 1-2 நிபந்தனை, AND லாஜிக் வழியாக எளியதாக வைக்க.",
      ],
    },
    exit: {
      title: "வெளியேற்ற உத்தி",
      tips: [
        "வெளியேற்றம் profit/loss எப்போது book ஆகும் என்று முடிவு செய்யும்.",
        "Stop Loss: எவ்வளவு நஷ்டம் ஏற்க முடியும் என்பதை வரையறுக்கும்.",
        "Target: லாபத்தை எப்போது book செய்வது — பேராசை வேண்டாம்.",
      ],
    },
    risk: {
      title: "ரிஸ்க் மேனேஜ்மென்ட்",
      tips: [
        "Position size மூலதனத்தில் 2–5%-ஐ விட அதிகமாக வேண்டாம்.",
        "Stop Loss எப்போதும் கட்டாயம் — இல்லாமல் ட்ரேட் வேண்டாம்.",
        "தினசரி loss limit அமைக்கவும் — உங்கள் மூலதனத்தை காப்பாற்றுங்கள்.",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "இண்டிகேட்டர் இணைத்தல்",
      tips: [
        "2–4 இண்டிகேட்டரின் கலவை சிறந்தது — over-fitting தவிர்க்கும்.",
        "Trend (EMA / MACD) + Momentum (RSI) வலுவான அடிப்படை.",
        "ஒரே family-ன் இண்டிகேட்டர் (RSI + Stochastic) தவிர்க்க — duplicate.",
      ],
    },
    entry: {
      title: "Multi-Condition நுழைவுகள்",
      tips: [
        "AND லாஜிக் கடினமானது — அனைத்து நிபந்தனைகளும் match ஆக வேண்டும்.",
        "OR லாஜிக் தளர்ந்தது — ஏதாவது ஒன்று match ஆனால் ட்ரேட்.",
        "Confirmation indicators (volume, ADX) entry-ஐ வலுப்படுத்தும்.",
      ],
    },
    exit: {
      title: "Smart வெளியேற்றங்கள்",
      tips: [
        "Trailing stop loss லாபத்தை lock செய்யும் price மேலே போகும் போது.",
        "Partial exit: half qty target-ல் close, மீதி trail செய்.",
        "Time-based exit: intraday-ஐ 15:15 IST-க்குள் square off செய்.",
      ],
    },
    risk: {
      title: "Position Sizing + ரிஸ்க்",
      tips: [
        "Lot size — strategy + capital + Stop Loss தூரத்திலிருந்து கணக்கிடுங்கள்.",
        "Per-trade ரிஸ்க்: capital-ல் 1% முதல் 2% வரை மட்டுமே.",
        "Max trades/day வரம்பு வைக்கவும் — over-trading-ல் நஷ்டம்.",
      ],
    },
  },
  expert: {
    indicators: {
      title: "Advanced Indicator Tuning",
      tips: [
        "Indicator periods-ஐ sensitivity-test செய் — robust values தேர்ந்தெடு.",
        "Custom params experiment செய்யலாம், ஆனால் walk-forward மூலம் validate.",
        "Experimental indicators (Donchian, ATR) Robustness tab-க்கு பின் மட்டுமே.",
      ],
    },
    entry: {
      title: "சிக்கலான Entry Logic",
      tips: [
        "Indicator + candle + price + time conditions ஒன்றாக சேர்க்கலாம்.",
        "AND/OR top-level operator — nested grouping-க்கு JSON tab பயன்படுத்த.",
        "Reverse-signal entry: அதே condition எதிர் பக்கம் trigger செய்யும்.",
      ],
    },
    exit: {
      title: "Multi-Stage வெளியேற்றங்கள்",
      tips: [
        "Partial + trailing + indicator-driven exits ஒன்றாக பயன்படுத்தலாம்.",
        "Square-off time intraday strategy-க்கு கட்டாயம்.",
        "Reverse-signal exit position-ஐ flip செய்யும் — directional strategies-க்கு.",
      ],
    },
    risk: {
      title: "ரிஸ்க் வரம்புகள் + Override",
      tips: [
        "Daily loss + max trades + capital-per-trade — மூன்று பாதுகாப்பு படிகள்.",
        "Max loss streak strategy-ஐ auto-pause trigger செய்யும்.",
        "Robustness toggle on வைக்க — sensitivity sweep கூடுதல் confidence.",
      ],
    },
    robustness: {
      title: "Walk-Forward + Sensitivity",
      tips: [
        "Walk-forward 5 வேறுபட்ட time windows-ல் test — out-of-sample check.",
        "Sensitivity ±10% parameter perturbation overfitting கண்டறியும்.",
        "இரண்டையும் enable செய்வது சிறந்தது — மெதுவான ஆனால் confident verdict.",
      ],
    },
    json: {
      title: "Raw JSON Editing",
      tips: [
        "JSON tab read+write — Apply-க்கு பின் builder state overwrite ஆகும்.",
        "Validate-on-blur schema errors-ஐ submission-க்கு முன் கண்டுபிடிக்கும்.",
        "Sync button text-ஐ builder state-லிருந்து refresh செய்யும் manual edits பின்.",
      ],
    },
  },
};


// ─── বাংলা (Bengali) ───────────────────────────────────────────────


const BENGALI_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "ইন্ডিকেটর কী?",
      tips: [
        "ইন্ডিকেটর চার্টের প্যাটার্ন দেখায় — যেমন EMA ট্রেন্ড দেখায়।",
        "শুরুতে 1-2 ইন্ডিকেটর যথেষ্ট — বেশি হলে কনফিউশন বাড়ে।",
        "জনপ্রিয়: RSI (overbought/oversold), EMA (ট্রেন্ড), MACD (মোমেন্টাম)।",
      ],
    },
    entry: {
      title: "এন্ট্রি কন্ডিশন",
      tips: [
        "এন্ট্রি কন্ডিশন ঠিক করে ট্রেড কখন খুলবে।",
        "সহজ: 'EMA 20 cross EMA 50' = ট্রেন্ড পরিবর্তনের সংকেত।",
        "শুরুতে 1-2 কন্ডিশন রাখো, AND লজিক দিয়ে সহজ রাখো।",
      ],
    },
    exit: {
      title: "এক্সিট কৌশল",
      tips: [
        "এক্সিট ঠিক করে প্রফিট/লস কখন বুক হবে।",
        "Stop Loss: সর্বোচ্চ কতটা ক্ষতি সহ্য করতে পারো।",
        "টার্গেট: লাভ কখন বুক করবে — লোভ কোরো না।",
      ],
    },
    risk: {
      title: "রিস্ক ম্যানেজমেন্ট",
      tips: [
        "Position size ক্যাপিটালের 2–5%-এর বেশি কখনই নয়।",
        "Stop Loss সর্বদা বাধ্যতামূলক — এটি ছাড়া ট্রেড কোরো না।",
        "দৈনিক লস লিমিট সেট করো — নিজের ক্যাপিটাল রক্ষা করো।",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "ইন্ডিকেটর সংযোজন",
      tips: [
        "2–4 ইন্ডিকেটরের মিশ্রণ সর্বোত্তম — over-fitting এড়ানো যায়।",
        "Trend (EMA / MACD) + Momentum (RSI)-এর কম্বো শক্তিশালী ভিত্তি।",
        "একই family-র ইন্ডিকেটর (RSI + Stochastic) এড়াও — redundant।",
      ],
    },
    entry: {
      title: "মাল্টি-কন্ডিশন এন্ট্রি",
      tips: [
        "AND লজিক কঠিন — সব কন্ডিশন match হতে হবে।",
        "OR লজিক শিথিল — যেকোনো একটি match হলে ট্রেড হয়।",
        "Confirmation ইন্ডিকেটর (volume, ADX) এন্ট্রিকে শক্তিশালী করে।",
      ],
    },
    exit: {
      title: "Smart এক্সিট",
      tips: [
        "Trailing Stop Loss প্রফিট lock করে যখন price উপরে যায়।",
        "Partial exit: অর্ধেক qty target-এ close, বাকি trail করো।",
        "Time-based exit: intraday-কে 15:15 IST-এর মধ্যে square off।",
      ],
    },
    risk: {
      title: "Position Sizing + রিস্ক",
      tips: [
        "Lot size — strategy + capital + Stop Loss দূরত্ব থেকে নির্ধারিত।",
        "Per-trade রিস্ক: capital-এর 1% থেকে 2% সর্বোচ্চ।",
        "Max trades/day সীমা রাখো — over-trading-এ ক্ষতি হয়।",
      ],
    },
  },
  expert: {
    indicators: {
      title: "Advanced Indicator Tuning",
      tips: [
        "Indicator periods-এর sensitivity-test করো — robust values পছন্দ করো।",
        "Custom params experiment করতে পারো, কিন্তু walk-forward দিয়ে validate।",
        "Experimental ইন্ডিকেটর (Donchian, ATR) Robustness tab-এর পর ব্যবহার করো।",
      ],
    },
    entry: {
      title: "জটিল Entry Logic",
      tips: [
        "Indicator + candle + price + time কন্ডিশন একসাথে combine করতে পারো।",
        "AND/OR top-level operator — nested grouping-এর জন্য JSON tab ব্যবহার।",
        "Reverse-signal entry: একই condition বিপরীত দিকে trigger করে।",
      ],
    },
    exit: {
      title: "Multi-Stage এক্সিট",
      tips: [
        "Partial + trailing + indicator-driven exit একসাথে ব্যবহার করতে পারো।",
        "Square-off time intraday strategy-র জন্য বাধ্যতামূলক।",
        "Reverse-signal exit position flip করে — directional strategy-র জন্য।",
      ],
    },
    risk: {
      title: "রিস্ক সীমা + Override",
      tips: [
        "Daily loss + max trades + capital-per-trade — তিনটি সুরক্ষা স্তর।",
        "Max loss streak strategy-কে auto-pause trigger করে।",
        "Robustness toggle on রাখো — sensitivity sweep অতিরিক্ত confidence।",
      ],
    },
    robustness: {
      title: "Walk-Forward + Sensitivity",
      tips: [
        "Walk-forward 5টি ভিন্ন time window-এ test করে — out-of-sample check।",
        "Sensitivity ±10% parameter perturbation overfitting ধরে।",
        "দুটোই enable করা ideal — slow but high-confidence verdict।",
      ],
    },
    json: {
      title: "Raw JSON Editing",
      tips: [
        "JSON tab read+write — Apply-এর পর builder state overwrite হয়।",
        "Validate-on-blur schema errors-কে submission-এর আগে ধরে।",
        "Sync button text-কে builder state থেকে refresh করে — manual edits-এর পর।",
      ],
    },
  },
};


// ─── Aggregate ─────────────────────────────────────────────────────────


export const COACHING_TIPS: Record<
  Language,
  Record<BuilderMode, CoachingTipsForMode>
> = {
  hinglish: HINGLISH_TIPS,
  english: ENGLISH_TIPS,
  hindi: HINDI_TIPS,
  gujarati: GUJARATI_TIPS,
  tamil: TAMIL_TIPS,
  bengali: BENGALI_TIPS,
};

export const WELCOME_MESSAGES: Record<
  Language,
  Record<BuilderMode, string>
> = {
  hinglish: {
    beginner:
      "Namaste! Strategy banane mein madad karu? Step-by-step le chalunga. 👋",
    intermediate:
      "Namaste! Saari sections ek saath visible hain — kahin bhi shuru kar sakte ho. 👋",
    expert:
      "Namaste! Expert mode mein full control hai. Tips dekho jab kahin doubt ho. 👋",
  },
  english: {
    beginner:
      "Welcome — I'm AlgoMitra, your trading mentor. We'll build a strategy step by step. 👋",
    intermediate:
      "Welcome back. All sections are open at once — start wherever you want, tips travel with you. 👋",
    expert:
      "Welcome. You know the engine — I'll surface a tip when a section needs one, otherwise stay out of your way. 👋",
  },
  hindi: {
    beginner:
      "नमस्ते! रणनीति बनाने में मदद करूँ? Step-by-step ले चलूँगा। 👋",
    intermediate:
      "नमस्ते! सारी sections एक साथ दिख रही हैं — कहीं भी शुरू कर सकते हो। 👋",
    expert:
      "नमस्ते! Expert mode में पूरा control है। Doubt हो तो tips देख लो। 👋",
  },
  gujarati: {
    beginner:
      "નમસ્તે! વ્યૂહરચના બનાવવામાં મદદ કરું? Step-by-step સાથે લઈ જઈશ. 👋",
    intermediate:
      "નમસ્તે! બધા sections એક સાથે દેખાય છે — ગમે ત્યાંથી શરૂ કરો. 👋",
    expert:
      "નમસ્તે! Expert mode માં સંપૂર્ણ control છે. Doubt હોય તો tips જુઓ. 👋",
  },
  tamil: {
    beginner:
      "வணக்கம்! உத்தி உருவாக்க உதவ வேண்டுமா? Step-by-step கூட்டிச் செல்வேன். 👋",
    intermediate:
      "வணக்கம்! எல்லா sections-ம் ஒரே நேரத்தில் தெரியும் — எங்கிருந்தும் ஆரம்பிக்க. 👋",
    expert:
      "வணக்கம்! Expert mode-ல் முழு கட்டுப்பாடு உண்டு. சந்தேகம் வந்தால் tips பார்க்க. 👋",
  },
  bengali: {
    beginner:
      "নমস্কার! কৌশল তৈরিতে সাহায্য করি? Step-by-step নিয়ে যাব। 👋",
    intermediate:
      "নমস্কার! সব sections একসাথে দেখা যাচ্ছে — যেকোনো জায়গা থেকে শুরু করো। 👋",
    expert:
      "নমস্কার! Expert mode-এ পুরো control আছে। সন্দেহ হলে tips দেখে নাও। 👋",
  },
};


/**
 * Resolve a (language, mode) pair to its tips, falling back to
 * Hinglish if the language doesn't ship coverage for the mode.
 * Defensive — every language ships full coverage today, but the
 * deferred-language batch may add languages incrementally.
 */
export function getTipsForModeAndLanguage(
  language: Language,
  mode: BuilderMode,
): CoachingTipsForMode {
  return COACHING_TIPS[language]?.[mode] ?? COACHING_TIPS.hinglish[mode];
}


/** Same fallback contract as :func:`getTipsForModeAndLanguage`. */
export function getWelcomeForModeAndLanguage(
  language: Language,
  mode: BuilderMode,
): string {
  return (
    WELCOME_MESSAGES[language]?.[mode] ?? WELCOME_MESSAGES.hinglish[mode]
  );
}
