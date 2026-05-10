"use client";

/**
 * /support/faq — static FAQ page.
 *
 * Hardcoded Q&A pairs in Hinglish. Phase 1 keeps these in
 * frontend code so launch-day support doesn't depend on a
 * separate CMS deploy. Phase 2 (knowledge-base CMS) will move
 * these into the backend with admin-editable content.
 */

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, BookOpen, ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface FaqItem {
  question: string;
  answer: string;
  topic: string;
}

const FAQS: ReadonlyArray<FaqItem> = [
  {
    question: "Strategy kaise banayein?",
    answer:
      "Strategies tab pe jao, 'Naya Strategy' click karo, aur teen modes mein se ek choose karo: Beginner (guided wizard, simplest), Intermediate (collapsible sections), ya Expert (full control). Beginner se shuru karo agar pehli baar bana rahe ho — AlgoMitra panel right side pe har step pe coaching tips deta hai.",
    topic: "Strategy",
  },
  {
    question: "Backtest kya hota hai?",
    answer:
      "Backtest matlab strategy ko historical data pe run karna — past data pe kaisi perform karti? Backtest results profit, drawdown, win rate, Sharpe ratio dikhate hain. Yeh sirf simulation hai — real performance alag ho sakti hai. Backtest pass hone ke baad Truth Engine + AI Advisor verdict zaroor check karo.",
    topic: "Backtest",
  },
  {
    question: "Live trading kab enable hoga?",
    answer:
      "Live trading enable hone ke liye 4 conditions chahiye: (1) ek broker connect kiya ho, (2) strategy ka 7+ paper-trading sessions complete hue ho, (3) Trust Score acceptable ho, (4) Truth Score pass kare. SafetyChain har order pe yeh checks run karta hai. Live trading global feature flag bhi hai — admin ne enable kiya hoga toh aapko per-user opt-in mil jayega.",
    topic: "Live Trading",
  },
  {
    question: "Broker connect kaise karein?",
    answer:
      "Brokers tab pe jao, 'Add Broker' click karo, aur Dhan / Fyers / Zerodha mein se chuno. App ID + Secret broker ke developer portal se milte hain — copy paste karo, OAuth flow complete karo, aur connection green ho jayega. Connection problems ho to support ticket file karo (Category: 'Broker Connection') — jaldi help milegi.",
    topic: "Broker",
  },
  {
    question: "Paper sessions kya hain aur kyun zaroori hain?",
    answer:
      "Paper sessions matlab strategy ko fake-money pe candle-by-candle test karna — broker se actual order nahi jaata, sirf simulation. 7 sessions ka rule hai live trading se pehle ki yeh maturity gate hai: backtest accha ho sakta hai but live tape pe strategy alag behave karti hai. 7 sessions complete hone ke baad SafetyChain ke baaki checks pass hote hain to live enable ho jaata hai.",
    topic: "Paper Trading",
  },
  {
    question: "AlgoMitra kya karta hai?",
    answer:
      "AlgoMitra aapka coaching companion hai — har builder mode ke har section pe context-aware tips deta hai. Right-side panel mein dikhta hai. 5 languages mein available: Hinglish, हिंदी, ગુજરાતી, தமிழ், বাংলা. Top header mein language switcher hai. Tips deterministic hain — same input par same advice (LLM nahi).",
    topic: "AlgoMitra",
  },
  {
    question: "Marketplace mein strategy kaise buy karein?",
    answer:
      "Marketplace tab pe browse karo — published strategies dikhengi. Listing detail pe Strategy Transparency Ledger panel hota hai jo daily snapshots ka cryptographic chain dikhata hai (90-day forward-test proof). 'Subscribe' click karo — free strategies turant subscribe ho jaati hain, paid mein abhi stub hai (real payment Phase 4 mein launch hoga).",
    topic: "Marketplace",
  },
  {
    question: "Strategy Transparency Ledger ka kya matlab hai?",
    answer:
      "Yeh master-prompt 'Backtest nahi, Proof' differentiator hai. Har published listing ka daily performance snapshot SHA-256 hash chain mein link ho jaata hai. Verify endpoint pure chain check kar leta hai — agar koi field tamper kare to verify FAIL ho jaata hai. Phase 4 mein yeh chain Polygon blockchain pe bhi commit hoga; abhi off-chain prototype hai (purely backend).",
    topic: "Marketplace",
  },
  {
    question: "Kill switch kya hai aur kaise reset karein?",
    answer:
      "Kill Switch ek safety circuit breaker hai — agar daily loss cap breach ho ya aap manually click karo to platform turant saare brokers pe pending orders cancel kar deta hai aur open positions square off ho jaati hain. Reset karne ke liye Kill Switch page pe jao, trip ka reason dekho, 'Acknowledge & Resume' click karo aur confirmation type karo. Reset ke baad audit log mein record ho jaata hai.",
    topic: "Safety",
  },
  {
    question: "Auto-priority categories kaise decide hote hain?",
    answer:
      "Support ticket file karte time category choose karo — backend automatic priority assign karta hai: Billing aur Broker Connection → High. Bug → High by default; description mein 'crash', 'data loss', 'cannot login' jaise critical keywords mile to → Critical. Account aur Strategy Help → Medium. Other → Low. Admin baad mein priority change kar sakte hain agar zaroorat ho.",
    topic: "Support",
  },
  {
    question: "Multi-language support kahaan-kahaan hai?",
    answer:
      "Phase 1 mein AlgoMitra coaching tips + welcome messages 5 languages mein hain (Hinglish default, plus Hindi, Gujarati, Tamil, Bengali). Marathi / Telugu / Kannada / Malayalam / Punjabi / Odia v1.1 mein aayenge. UI ke baaki strings (buttons, labels) abhi mostly English / Hinglish hain — full UI translation v1.1 mein.",
    topic: "AlgoMitra",
  },
  {
    question: "Pine script import karne ka tarika kya hai?",
    answer:
      "Strategies > Import from Pine pe paste karo apna Pine v5 source. Importer 31+ ta.* indicators recognise karta hai aur baaki ko coming-soon notes ke saath flag kar deta hai. License header (MIT/BSD/Apache) auto-detect ho jaata hai; restrictive licenses pe yellow warning aata hai 'apne paas right hai confirm karo'. Backend mein zero eval/exec/compile — purely textual conversion.",
    topic: "Pine Importer",
  },
  {
    question: "AI Doctor ka 'Apply Fix' kab use karein?",
    answer:
      "Backtest results mein Doctor panel diagnose karta hai (e.g. 'missing stop loss', 'overfitting detected', 'low truth score'). Agar fix mechanical hai (e.g. add stop loss, reduce indicators) to Doctor 'improvedStrategyDraft' generate kar deta hai. 'Apply Fix & Compare' click karo — backend dono backtests parallel mein run karega aur side-by-side diff dikha dega. Apply karne se pehle compare zaroor karo.",
    topic: "AI",
  },
  {
    question: "Tickets ka response time kya hai?",
    answer:
      "Phase 1 mein admin team manually queue dekhti hai — usually 24-48 hours mein reply. Critical priority tickets (data loss, login locked out, broker disconnect) faster handle hote hain. Phase 2 mein live chat + auto-routing aayega. Apne ticket ka status 'Mere Tickets' tab pe dikhe ga — open / in_progress / awaiting_user / resolved / closed.",
    topic: "Support",
  },
  {
    question: "Mobile pe kaisa kaam karta hai?",
    answer:
      "Major pages (Strategies list, Backtest results, Marketplace browse, Login/Register) mobile-friendly hain. Sidebar mobile pe hidden ho jaata hai aur bottom-tab nav aa jaati hai. Expert builder dense layout hai — mobile pe usable but desktop preferred. Issues report karo support mein — actively polish kar rahe hain.",
    topic: "Mobile",
  },
  {
    question: "Trust Score kya hota hai?",
    answer:
      "Trust Score (0-100) batata hai strategy ka risk profile aur historical reliability — high score matlab consistent behavior, low drawdown, sustainable returns. Calculation backtest stats + paper trading consistency + walk-forward results se hoti hai. Live trading enable hone ke liye acceptable Trust Score chahiye. Builder result panel pe number plus 'kya bana isko risky/safe' breakdown bhi dikhta hai.",
    topic: "Trust & Truth",
  },
  {
    question: "Truth Score kya batata hai?",
    answer:
      "Truth Score check karta hai strategy 'looks too good' to nahi hai — overfitting, lookahead bias, survivorship bias, in-sample over-tuning. Score Pass / Warning / Fail mein aata hai. Pass ke liye walk-forward, parameter sensitivity, out-of-sample reliability sab cross-checked hote hain. Truth FAIL hone pe live trading block ho jaati hai — 'paper accha lag raha hai' real proof nahi hai.",
    topic: "Trust & Truth",
  },
  {
    question: "Strategy Versioning kya hai aur rollback kaise karein?",
    answer:
      "Har strategy save pe ek version automatic create ho jaati hai (v1, v2, v3...) — change_summary ke saath. Strategy detail page pe 'Version History' panel mein puri timeline dikhega aur kisi bhi version pe 'Rollback' click karke wapas us state pe ja sakte ho. Rollback ek naya version banaata hai (purani delete nahi hoti) — audit log mein record ho jaata hai. Backtest results version-pinned hote hain.",
    topic: "Versioning",
  },
  {
    question: "Marketplace mein apni strategy kaise list karein?",
    answer:
      "Phase 1 mein creator role chahiye — admin se request karo (Settings → 'Become a Creator'). Approval ke baad Strategies tab pe '...' menu mein 'Publish to Marketplace' aata hai. Title, description, tags, price (free ya paid), aur strategy version select karo. Pehle 'Draft' status mein save hoti hai — preview verify karke 'Publish' karo. Listing live hone ke baad daily snapshots Transparency Ledger mein automatic add hote hain.",
    topic: "Marketplace",
  },
  {
    question: "Broker Execution Guard kya block karta hai?",
    answer:
      "Execution Guard SafetyChain ka last layer hai — broker ke pass jaane se pehle har order check karta hai: (1) market hours hai ya nahi, (2) symbol allowed-list mein hai, (3) order size max-position-cap ke andar, (4) daily loss cap breach toh nahi hua, (5) kill switch tripped to nahi. Koi bhi check fail hone pe order silently dropped + audit log mein 'execution_blocked' entry. Frontend mein Toast notification milti hai.",
    topic: "Safety",
  },
  {
    question: "Apna data delete kar sakte hain?",
    answer:
      "Haan — DPDP Act compliance ke liye account aur saara data delete karne ka right hai. Settings → Privacy → 'Delete Account' click karo, password confirm karo. Account turant disabled ho jaata hai aur 30 din ke andar saara personal data (strategies, trades, audit logs except legally-required) hard-delete ho jaata hai. Marketplace pe published listings agar hain to pehle archive karo. Process irreversible hai — backup chahiye to pehle export karo.",
    topic: "Privacy",
  },
  {
    question: "Refund policy kya hai?",
    answer:
      "Phase 1 launch ke time platform free hai (no subscription fees). Marketplace paid strategies abhi stub mode mein hain — actual payment Phase 4 mein launch hoga, aur tab refund policy publish hogi (industry standard: 7-day no-questions-asked for non-consumed access). Broker side ke charges TRADETRI ke control mein nahi hain — wo broker ke terms apply hote hain. Billing-related koi bhi confusion ho to support ticket file karo (Category: Billing).",
    topic: "Billing",
  },
  {
    question: "Auto Kill Switch kab activate hota hai?",
    answer:
      "Kill Switch automatic trip ho jaata hai jab: (1) daily loss cap breach hota hai (default 2% of capital, settings mein adjust kar sakte ho), (2) consecutive 3 orders rejected ho broker se, (3) admin manually trip kare via /admin/kill-switch endpoint, (4) heartbeat 60 second se zyada miss ho jaaye. Trip hone ke baad saare pending orders cancel + open positions square off ho jaate hain. Reset manual hai — Kill Switch page pe acknowledge karna padta hai.",
    topic: "Safety",
  },
];

const TOPICS = Array.from(new Set(FAQS.map((f) => f.topic))).sort();

export default function FaqPage() {
  const [search, setSearch] = useState("");
  const [topicFilter, setTopicFilter] = useState<string | null>(null);

  const filtered = FAQS.filter((f) => {
    if (topicFilter != null && f.topic !== topicFilter) return false;
    if (search.trim() === "") return true;
    const q = search.trim().toLowerCase();
    return (
      f.question.toLowerCase().includes(q) ||
      f.answer.toLowerCase().includes(q) ||
      f.topic.toLowerCase().includes(q)
    );
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-5"
    >
      <Link
        href="/support"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to Help Center
      </Link>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6 text-accent-blue" />
          FAQ
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          {FAQS.length} most-asked questions ka answer. Yahan na
          mile to support ticket file kar do — 24-48 ghante mein
          reply mil jayega.
        </p>
      </header>

      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search FAQ..."
          />
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              type="button"
              onClick={() => setTopicFilter(null)}
              className={cn(
                "rounded-md px-2 py-1 text-[10px] uppercase tracking-wide transition-colors",
                topicFilter === null
                  ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                  : "bg-white/[0.04] text-muted-foreground border border-white/[0.06] hover:bg-white/[0.06]",
              )}
            >
              All
            </button>
            {TOPICS.map((topic) => (
              <button
                key={topic}
                type="button"
                onClick={() => setTopicFilter(topic)}
                className={cn(
                  "rounded-md px-2 py-1 text-[10px] uppercase tracking-wide transition-colors",
                  topicFilter === topic
                    ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                    : "bg-white/[0.04] text-muted-foreground border border-white/[0.06] hover:bg-white/[0.06]",
                )}
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      </GlassmorphismCard>

      {filtered.length === 0 ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm">
            Koi match nahi mila. Search query alag try karo, ya
            support ticket file kar do.
          </p>
        </GlassmorphismCard>
      ) : (
        <div className="space-y-2">
          {filtered.map((faq) => (
            <FaqRow key={faq.question} faq={faq} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

function FaqRow({ faq }: { faq: FaqItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <GlassmorphismCard hover={false}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left space-y-2"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <p className="text-sm font-semibold">{faq.question}</p>
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              {faq.topic}
            </Badge>
          </div>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 text-muted-foreground shrink-0 mt-1 transition-transform",
              expanded && "rotate-180",
            )}
          />
        </div>
        {expanded ? (
          <p className="text-[12px] text-foreground/90 leading-relaxed">
            {faq.answer}
          </p>
        ) : null}
      </button>
    </GlassmorphismCard>
  );
}
