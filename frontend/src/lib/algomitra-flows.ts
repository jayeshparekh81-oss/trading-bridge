/**
 * AlgoMitra conversation flows (Phase 1A — pre-defined state machines).
 *
 * Each flow is a graph of steps. Each step has assistant text plus
 * optional quick-action buttons; tapping a button transitions the chat
 * to the next step or fires a side-effect (image upload, escalation,
 * external link).
 *
 * Phase 1B will let Claude pick steps dynamically; the flow IDs we use
 * here become the system prompt's "tool" set.
 */

export type FlowAction =
  | { kind: "next"; nextStep: string }
  | { kind: "request_image" }
  | { kind: "open_url"; url: string }
  | { kind: "escalate"; channel: "whatsapp" | "calendly" | "email" }
  | { kind: "switch_flow"; flowId: FlowId; nextStep?: string }
  | { kind: "end" }
  | { kind: "restart" };

export interface FlowOption {
  label: string;
  emoji?: string;
  action: FlowAction;
}

export interface FlowStep {
  id: string;
  /**
   * Assistant message. May contain `{userName}` token which the renderer
   * replaces from auth context. Plain text — the bubble component
   * renders newlines.
   */
  message: string;
  options?: readonly FlowOption[];
  /** Optional helper note shown below quick actions, smaller font. */
  note?: string;
}

export type FlowId = "welcome" | "setup" | "error" | "education" | "support";

export interface Flow {
  id: FlowId;
  name: string;
  /** Step ID where the flow begins. */
  start: string;
  steps: Record<string, FlowStep>;
}

// ═══════════════════════════════════════════════════════════════════════
// Flow A — Welcome
// ═══════════════════════════════════════════════════════════════════════

const welcomeFlow: Flow = {
  id: "welcome",
  name: "New User Welcome",
  start: "greet",
  steps: {
    greet: {
      id: "greet",
      message:
        "Namaste {userName}! Main AlgoMitra hoon — TRADETRI ka 24/7 saathi. 15 saal markets mein bitaaye hain, ab tujhe support karna hai.\n\nBata bhai, tu trader kaisa hai?",
      options: [
        {
          label: "Naya hoon, abhi seekh raha",
          emoji: "🌱",
          action: { kind: "next", nextStep: "newbie" },
        },
        {
          label: "Manual trade karta hoon",
          emoji: "👨‍💻",
          action: { kind: "next", nextStep: "manual" },
        },
        {
          label: "Algo experienced hoon",
          emoji: "⚡",
          action: { kind: "next", nextStep: "experienced" },
        },
      ],
    },
    newbie: {
      id: "newbie",
      message:
        "Mast! Naya hai matlab koi galat aadat nahi pakdi — yahi best position hai seekhne ki. 🌱\n\nMera suggestion:\n1. Pehle paper mode mein 2 hafte trade kar\n2. Risk management rules pakke kar le\n3. Phir choti capital se live jaa\n\nKaha se start karen?",
      options: [
        {
          label: "Broker connect karna hai",
          emoji: "🔌",
          action: { kind: "switch_flow", flowId: "setup" },
        },
        {
          label: "Trading basics samjha",
          emoji: "📚",
          action: { kind: "switch_flow", flowId: "education" },
        },
        {
          label: "Founder se baat karaa",
          emoji: "👤",
          action: { kind: "escalate", channel: "calendly" },
        },
      ],
    },
    manual: {
      id: "manual",
      message:
        "Mast — manual experience golden hai. Ab automation pe shift karna emotion ka biggest enemy hata dega.\n\nTRADETRI tujhe 3 cheezein degi: speed (sub-second), discipline (kill switch), aur audit trail. Kaha se start karen?",
      options: [
        {
          label: "Broker setup karwa",
          emoji: "🔌",
          action: { kind: "switch_flow", flowId: "setup" },
        },
        {
          label: "Paper mode kaise on karen",
          emoji: "📝",
          action: { kind: "switch_flow", flowId: "education", nextStep: "paper" },
        },
        {
          label: "Strategy bana ke dikhao",
          emoji: "🎯",
          action: { kind: "open_url", url: "/strategies" },
        },
      ],
    },
    experienced: {
      id: "experienced",
      message:
        "Wah! Algo trader se baat karna alag hi maza hai. 🚀\n\nTRADETRI ka USP: TradingView webhooks → Indian brokers, sub-second latency, full kill switch + audit trail. Multi-broker (Fyers + Dhan live, Zerodha Phase 2).\n\nKya chahiye?",
      options: [
        {
          label: "Multi-broker setup",
          emoji: "🔀",
          action: { kind: "switch_flow", flowId: "setup" },
        },
        {
          label: "Architecture / latency details",
          emoji: "⚙️",
          action: { kind: "escalate", channel: "calendly" },
        },
        {
          label: "Custom integration chahiye",
          emoji: "🛠️",
          action: { kind: "escalate", channel: "whatsapp" },
        },
      ],
    },
  },
};

// ═══════════════════════════════════════════════════════════════════════
// Flow B — Setup help
// ═══════════════════════════════════════════════════════════════════════

const setupFlow: Flow = {
  id: "setup",
  name: "Broker Setup Help",
  start: "pick_broker",
  steps: {
    pick_broker: {
      id: "pick_broker",
      message: "Bata bhai, kaun sa broker connect karna hai?",
      options: [
        { label: "Fyers", emoji: "🟢", action: { kind: "next", nextStep: "fyers_step1" } },
        { label: "Dhan", emoji: "🔵", action: { kind: "next", nextStep: "dhan_step1" } },
        { label: "Zerodha", emoji: "🟠", action: { kind: "next", nextStep: "zerodha_pending" } },
        { label: "Doosra broker", emoji: "❓", action: { kind: "next", nextStep: "other_broker" } },
      ],
    },
    fyers_step1: {
      id: "fyers_step1",
      message:
        "Fyers ke liye 2 cheezein chahiye: App ID aur App Secret.\n\nStep 1: Fyers Dashboard mein login kar (myapi.fyers.in).\nStep 2: 'My Apps' tab kholo.\nStep 3: Apna app dikhega — agar nahi hai toh 'Create New App' click kar (redirect URL: kuch bhi placeholder de sakte ho).\n\nReady? Next step batata hoon.",
      options: [
        { label: "Ready, aage chal", emoji: "✅", action: { kind: "next", nextStep: "fyers_step2" } },
        { label: "Screenshot bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
        { label: "Atak gaya — founder se baat", action: { kind: "escalate", channel: "whatsapp" } },
      ],
    },
    fyers_step2: {
      id: "fyers_step2",
      message:
        "Step 4: App ID copy kar (jaise VZCA6T6Z6O-100).\nStep 5: 'APP SECRET' column mein 'Show' click → secret copy kar.\nStep 6: TRADETRI → Brokers → Add Broker → Fyers select kar.\nStep 7: Dono values paste kar de aur save.\n\nKaam ho gaya na?",
      options: [
        { label: "Haan, connected!", emoji: "🎉", action: { kind: "next", nextStep: "celebrate" } },
        { label: "Error aaya", emoji: "⚠️", action: { kind: "switch_flow", flowId: "error" } },
        { label: "Stuck — image bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
      ],
    },
    dhan_step1: {
      id: "dhan_step1",
      message:
        "Dhan setup easier hai — sirf 2 fields chahiye: Client ID + Personal Access Token.\n\nStep 1: DhanHQ web mein login kar.\nStep 2: My Profile → 'Access DhanHQ Trading APIs' click kar.\nStep 3: 'Generate Token' button click kar.\n\nReady?",
      options: [
        { label: "Ready, aage chal", emoji: "✅", action: { kind: "next", nextStep: "dhan_step2" } },
        { label: "Screenshot bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
      ],
    },
    dhan_step2: {
      id: "dhan_step2",
      message:
        "Step 4: Token + Client ID copy kar le (token sirf ek baar dikhega — store karna safe jagah pe).\nStep 5: TRADETRI → Brokers → Add Broker → Dhan select kar.\nStep 6: Client ID + Access Token paste kar.\n\nNote: Dhan token expire hota hai. Connection fail ho toh new token generate karke replace karna padega.",
      options: [
        { label: "Hogaya!", emoji: "🎉", action: { kind: "next", nextStep: "celebrate" } },
        { label: "Error aa raha hai", emoji: "⚠️", action: { kind: "switch_flow", flowId: "error" } },
      ],
    },
    zerodha_pending: {
      id: "zerodha_pending",
      message:
        "Zerodha Phase 2 mein aa raha hai (~6-8 hafte). Tab tak option:\n1. Fyers/Dhan pe paper trade karke setup test kar le\n2. Calendly pe slot book kar — beta access pehle de denge",
      options: [
        { label: "Fyers try karta hoon", emoji: "🟢", action: { kind: "next", nextStep: "fyers_step1" } },
        { label: "Beta access chahiye", emoji: "🚀", action: { kind: "escalate", channel: "calendly" } },
      ],
    },
    other_broker: {
      id: "other_broker",
      message:
        "Currently Fyers aur Dhan live hain. Shoonya, Zerodha, Upstox, AngelOne queue mein hain. Tu kaun sa use kar raha hai? WhatsApp pe bata, founder priority bump kar dega.",
      options: [
        { label: "WhatsApp pe baat", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
        { label: "Wapas options dikha", action: { kind: "next", nextStep: "pick_broker" } },
      ],
    },
    celebrate: {
      id: "celebrate",
      message:
        "Wah bhai! 🎉 Pehla broker connected. Ab next step:\n1. Webhook bana (Webhooks page)\n2. Strategy create kar — webhook + broker link kar\n3. Paper mode pe ek week test kar\n\nKisi mein help chahiye?",
      options: [
        { label: "Webhook setup", emoji: "🔗", action: { kind: "open_url", url: "/webhooks" } },
        { label: "Strategy banaa", emoji: "🎯", action: { kind: "open_url", url: "/strategies" } },
        { label: "Bas, thanks!", emoji: "👍", action: { kind: "end" } },
      ],
    },
  },
};

// ═══════════════════════════════════════════════════════════════════════
// Flow C — Error diagnosis
// ═══════════════════════════════════════════════════════════════════════

const errorFlow: Flow = {
  id: "error",
  name: "Error Diagnosis",
  start: "pick_error",
  steps: {
    pick_error: {
      id: "pick_error",
      message:
        "Theek hai bhai, debug karte hain. Error type kaunsa hai? Agar exact match nahi mil raha toh screenshot bhej de — main analyze kar deta hoon.",
      options: [
        { label: "Order place nahi ho raha", emoji: "🚫", action: { kind: "next", nextStep: "order_fail" } },
        { label: "Session expired error", emoji: "⏰", action: { kind: "next", nextStep: "session_expired" } },
        { label: "Insufficient funds", emoji: "💰", action: { kind: "next", nextStep: "funds" } },
        { label: "Invalid symbol", emoji: "❓", action: { kind: "next", nextStep: "symbol" } },
        { label: "Webhook fire nahi ho raha", emoji: "📡", action: { kind: "next", nextStep: "webhook_silent" } },
        { label: "Screenshot bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
      ],
    },
    order_fail: {
      id: "order_fail",
      message:
        "Order fail ke 5 main reasons:\n1. Margin shortage — broker account check kar\n2. Galat symbol format — F&O strike/expiry sahi hai?\n3. Session expired — broker reconnect kar\n4. Market hours ke baahar — 9:15-15:30 IST\n5. Kill switch tripped — daily loss limit hit\n\nKaunsa applicable hai? Screenshot bhej toh exact diagnose karoonga.",
      options: [
        { label: "Screenshot bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
        { label: "Founder se baat", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
        { label: "Sab try kar liya, fail", action: { kind: "escalate", channel: "calendly" } },
      ],
    },
    session_expired: {
      id: "session_expired",
      message:
        "Easy fix:\n1. Brokers page jao\n2. Apne broker ke saamne 'Reconnect' click kar\n3. Fyers ho toh OAuth dobara karna padega\n4. Dhan ho toh fresh access token paste karna hoga\n\nDhan ka token expire hota hai daily-ish — yaad rakh.",
      options: [
        { label: "Brokers page khol", emoji: "🔌", action: { kind: "open_url", url: "/brokers" } },
        { label: "Phir bhi nahi ho raha", action: { kind: "escalate", channel: "whatsapp" } },
      ],
    },
    funds: {
      id: "funds",
      message:
        "Bhai 3 things check kar:\n1. Trading account mein actual cash kitna hai? (broker app mein dekh)\n2. Pending orders to nahi block kar rahe margin?\n3. F&O ka margin requirement zyada hota hai — specially expiry day pe.\n\nT+1 settlement bhi yaad rakh — kal becha toh aaj usable hai.",
      options: [
        { label: "Funds page kholun", action: { kind: "open_url", url: "/dashboard" } },
        { label: "Founder se discuss", action: { kind: "escalate", channel: "calendly" } },
      ],
    },
    symbol: {
      id: "symbol",
      message:
        "Symbol format broker-specific hota hai:\n- Fyers NSE equity: RELIANCE-EQ\n- Dhan NSE equity: RELIANCE\n- F&O: NIFTY25APR25000CE format (year-month-strike-type)\n\nExact symbol jo bhej raha hai, mujhe paste kar — fix kar deta hoon.",
      options: [
        { label: "Screenshot bhejta hoon", emoji: "📸", action: { kind: "request_image" } },
        { label: "Founder se baat", action: { kind: "escalate", channel: "whatsapp" } },
      ],
    },
    webhook_silent: {
      id: "webhook_silent",
      message:
        "Webhook silent ho toh ye check kar:\n1. TradingView alert active hai? (paused na ho)\n2. Webhook URL exact paste kiya hai?\n3. JSON message format sahi hai?\n4. TRADETRI → Webhooks page → 'Test' button hit kar — wo work karta hai?\n\nTest pass ho raha aur TradingView se nahi aa raha — wo TradingView side ka issue hai.",
      options: [
        { label: "Webhook test karu", action: { kind: "open_url", url: "/webhooks" } },
        { label: "JSON format dikha", action: { kind: "next", nextStep: "json_template" } },
        { label: "Founder se baat", action: { kind: "escalate", channel: "whatsapp" } },
      ],
    },
    json_template: {
      id: "json_template",
      message:
        "TradingView alert message field mein yeh paste kar:\n\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"product_type\": \"INTRADAY\",\n  \"quantity\": 50\n}\n\nDouble quotes important hain. Symbol exact format mein bhej.",
      options: [
        { label: "Try karta hoon", action: { kind: "end" } },
        { label: "Phir bhi atka hoon", action: { kind: "escalate", channel: "whatsapp" } },
      ],
    },
  },
};

// ═══════════════════════════════════════════════════════════════════════
// Flow D — Trading education
// ═══════════════════════════════════════════════════════════════════════

const educationFlow: Flow = {
  id: "education",
  name: "Trading Education",
  start: "topic",
  steps: {
    topic: {
      id: "topic",
      message: "Bhai education ka time — kya seekhna hai?",
      options: [
        { label: "Risk management basics", emoji: "🛡️", action: { kind: "next", nextStep: "risk" } },
        { label: "Position sizing kaise", emoji: "📏", action: { kind: "next", nextStep: "sizing" } },
        { label: "Paper trading kya hai", emoji: "📝", action: { kind: "next", nextStep: "paper" } },
        { label: "Stop loss types", emoji: "🚦", action: { kind: "next", nextStep: "sl_types" } },
        { label: "Indian market timings", emoji: "🕒", action: { kind: "next", nextStep: "market_hours" } },
      ],
    },
    risk: {
      id: "risk",
      message:
        "🛡️ Risk Management — Trader's biggest weapon!\n\n15 saal me sikha — strategy 20% hai, risk management 80% hai trading me.\n\n3 golden rules:\n\n1. Per Trade Risk: Max 1-2% of capital\n   ₹50,000 capital = ₹500-1000 max risk per trade\n\n2. Daily Loss Limit: Max 5% of capital\n   Hit ho gaya = trading band, kal naya din\n\n3. Position Sizing: Calculate before entry\n   Risk amount ÷ Stop loss points = quantity\n\nWant detailed example with calculations?",
      options: [
        { label: "Show example", emoji: "🧮", action: { kind: "next", nextStep: "risk_example" } },
        { label: "Position sizing formula", emoji: "📏", action: { kind: "next", nextStep: "sizing" } },
        { label: "Daily limits guide", emoji: "🛑", action: { kind: "next", nextStep: "daily_limits" } },
        { label: "Kill switch enable karu", emoji: "⚡", action: { kind: "open_url", url: "/kill-switch" } },
      ],
    },
    risk_example: {
      id: "risk_example",
      message:
        "Real example, step-by-step:\n\nCapital: ₹2,00,000\nPer-trade risk: 1% = ₹2,000\n\nSetup: NIFTY 25000 CE buy\nEntry: ₹100\nStop Loss: ₹80\nRisk per unit: ₹100 - ₹80 = ₹20\n\nQuantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): -₹2,000 (1% of capital)\n50 baar lagatar SL hit ho toh bhi capital safe — discipline ka beauty yahi hai.",
      options: [
        { label: "Position sizing formula", emoji: "📏", action: { kind: "next", nextStep: "sizing" } },
        { label: "Daily limits guide", emoji: "🛑", action: { kind: "next", nextStep: "daily_limits" } },
        { label: "Bas, samjh gaya", emoji: "👍", action: { kind: "end" } },
      ],
    },
    daily_limits: {
      id: "daily_limits",
      message:
        "Daily loss limit = trading ka circuit breaker.\n\nRule: 5% se zyada loss ek din mein NEVER. Limit hit hote hi:\n• Sab open positions square off\n• Pending orders cancel\n• Naye orders block — agle din 9 AM tak\n\n15 saal ka observation: revenge trading ek hi din mein 30% account khaali kar sakti hai. Daily limit usse bachata hai.\n\nKill switch settings me set kar de — automatic enforce hoga.",
      options: [
        { label: "Kill switch open kar", emoji: "⚡", action: { kind: "open_url", url: "/kill-switch" } },
        { label: "Risk rules dobara", action: { kind: "next", nextStep: "risk" } },
        { label: "Done", emoji: "👍", action: { kind: "end" } },
      ],
    },
    sizing: {
      id: "sizing",
      message:
        "📏 Position Sizing — formula simple, discipline tough.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nReal example:\n• Capital: ₹2,00,000\n• Risk per trade: 1% = ₹2,000\n• Entry: ₹100, SL: ₹80\n• Risk per unit: ₹20\n• Quantity: 2,000 / 20 = 100 units\n\nGut feel pe size mat decide kar — math pe kar. Discipline = consistency.",
      options: [
        { label: "Show full example", emoji: "🧮", action: { kind: "next", nextStep: "risk_example" } },
        { label: "Risk rules dobara", action: { kind: "next", nextStep: "risk" } },
        { label: "Smajh gaya, thanks", emoji: "👍", action: { kind: "end" } },
      ],
    },
    paper: {
      id: "paper",
      message:
        "Paper trading = real signals, fake orders.\n\n• Strategy edit kar → 'Paper Mode' toggle on\n• Signals normal aate rahenge\n• Orders log mein dikhenge but broker pe nahi jayenge\n\n15 saal ka rule: minimum 2 hafte paper mode pe nai strategy chala. Math test pakka, emotion test live mein hi hota hai but math wahan bhi clear ho jaata hai.",
      options: [
        { label: "Strategies page khol", action: { kind: "open_url", url: "/strategies" } },
        { label: "Risk rules sikha", action: { kind: "next", nextStep: "risk" } },
      ],
    },
    sl_types: {
      id: "sl_types",
      message:
        "2 main types:\n\nSL (Stop Loss Limit):\n- Trigger price hit ho toh SL active\n- Limit price pe execute hota hai\n- Slippage protected, lekin gap pe miss ho sakta hai\n\nSL-M (Stop Loss Market):\n- Trigger pe MARKET order trigger\n- Slippage possible, but fill guaranteed\n\nVolatile market = SL-M (warna SL miss ho jata hai).\nCalm market = SL theek hai.",
      options: [
        { label: "Order types dobara samjha", action: { kind: "next", nextStep: "topic" } },
        { label: "Bas, samjh gaya", action: { kind: "end" } },
      ],
    },
    market_hours: {
      id: "market_hours",
      message:
        "Indian market schedule:\n\n• Pre-open: 9:00 - 9:08 IST\n• Equity: 9:15 - 15:30 IST\n• Block deal window: 8:45 - 9:00 / 14:05 - 14:20\n• MCX: 9:00 - 23:30 IST\n• Currency: 9:00 - 17:00 IST\n• Muhurat: special Diwali evening session\n\nT+1 settlement India mein lagu hai (most efficient global market!).",
      options: [
        { label: "Aur topics", action: { kind: "next", nextStep: "topic" } },
        { label: "Done", action: { kind: "end" } },
      ],
    },
  },
};

// ═══════════════════════════════════════════════════════════════════════
// Flow E — Emotional support
// ═══════════════════════════════════════════════════════════════════════

const supportFlow: Flow = {
  id: "support",
  name: "Emotional Support",
  start: "mood",
  steps: {
    mood: {
      id: "mood",
      message: "Bhai, kya feel ho raha hai abhi? Honest jawab de — judge nahi karunga.",
      options: [
        { label: "Loss day, frustrated", emoji: "😞", action: { kind: "next", nextStep: "loss_intake" } },
        { label: "Win streak, excited", emoji: "🔥", action: { kind: "next", nextStep: "win" } },
        { label: "Burnout feel ho raha", emoji: "😴", action: { kind: "next", nextStep: "burnout" } },
        { label: "Confused / overwhelmed", emoji: "🌀", action: { kind: "next", nextStep: "confused" } },
      ],
    },
    loss_intake: {
      id: "loss_intake",
      message:
        "Bhai, loss ki baat sun ke dukh hua. 💚\n\nPehle ek baat batao — aaj ka loss kitna hai aur kya feeling aa rahi hai?\n\nMain yahan hoon, judge nahi karunga. Sirf support.",
      options: [
        { label: "Frustrated", emoji: "😤", action: { kind: "next", nextStep: "frustrated" } },
        { label: "Want to revenge trade", emoji: "🔥", action: { kind: "next", nextStep: "revenge" } },
        { label: "Confused why happened", emoji: "❓", action: { kind: "next", nextStep: "confused_why" } },
        { label: "Want to take break", emoji: "🌿", action: { kind: "next", nextStep: "want_break" } },
      ],
    },
    frustrated: {
      id: "frustrated",
      message:
        "Frustration valid hai bhai. Loss ka pehla reaction yahi hota hai.\n\nEk kaam kar abhi:\n1. 5 min phone band kar\n2. Pani pi le, deep breath le\n3. Frustration ka 1 sentence likh — bus expression nikaal\n\nFir wapas aa, ek shaant mind se review karte hain. Kal trade hai, aaj nahi.",
      options: [
        { label: "Ho gaya, ab kya karen", action: { kind: "next", nextStep: "loss" } },
        { label: "Founder se baat", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
        { label: "Theek hai, break", action: { kind: "end" } },
      ],
    },
    revenge: {
      id: "revenge",
      message:
        "Bhai. STOP. 🛑\n\nRevenge trade = account ki funeral. 15 saal mein maine dekha — 90% blow-ups revenge se hote hain, strategy se nahi.\n\nAbhi yeh kar:\n1. Kill switch trigger kar de — naye orders block ho jayenge\n2. Trading screen band kar\n3. Apne aap se ek wada — 24 ghante koi trade nahi\n\nCapital bachana > revenge. Promise kar?",
      options: [
        { label: "Kill switch trigger kar", emoji: "⚡", action: { kind: "open_url", url: "/kill-switch" } },
        { label: "Founder ko WhatsApp", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
        { label: "Promise — break le raha", action: { kind: "next", nextStep: "loss" } },
      ],
    },
    confused_why: {
      id: "confused_why",
      message:
        "Mast — yeh sahi sawaal hai. Loss ka analysis hi next win ka foundation hai.\n\n3 cheez review kar, ekdum honest:\n1. Setup theek tha? — ya FOMO mein entry liya?\n2. SL pre-defined tha? — ya hope pe hold kiya?\n3. Position size sahi tha? — ya zyada bada chala?\n\nAgar kisi mein bhi 'nahi' hai — wo lesson hai. Journal mein likh, kal usse avoid kar.",
      options: [
        { label: "Risk rules dobara sikha", action: { kind: "switch_flow", flowId: "education", nextStep: "risk" } },
        { label: "Founder se discuss", emoji: "📅", action: { kind: "escalate", channel: "calendly" } },
        { label: "Done, journal likh raha", action: { kind: "end" } },
      ],
    },
    want_break: {
      id: "want_break",
      message:
        "Best decision bhai. Break = strength, weakness nahi.\n\n• Sab strategies pause kar de aaj\n• 24-48 ghante screen se door\n• Family ke saath time, gym, sleep — basics\n\nMarket bhaagega nahi. Tu rahega toh kal trade karega. Kill switch ka use kar — automatic enforcement hai.",
      options: [
        { label: "Strategies pause karu", action: { kind: "open_url", url: "/strategies" } },
        { label: "Kill switch kholu", emoji: "⚡", action: { kind: "open_url", url: "/kill-switch" } },
        { label: "Done, jaa raha hoon", emoji: "🌿", action: { kind: "end" } },
      ],
    },
    loss: {
      id: "loss",
      message:
        "Bhai, ruk. Saans le. 🌬️\n\n15 saal mein maine dekha hai — best traders unhone hi paaye jo loss ke baad break liya, revenge trade nahi.\n\nAbhi 3 cheezein kar:\n1. Trading screen band kar\n2. Family ke saath 30 min bita\n3. Kal ek journal entry likh — kya hua, kyun hua, lesson kya hai\n\nKill switch reset agle din 9 AM pe automatic hota hai. Aaj rest day hai.",
      options: [
        { label: "Founder se baat karni hai", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
        { label: "Risk rules dobara samjha", action: { kind: "switch_flow", flowId: "education", nextStep: "risk" } },
        { label: "Theek hai, break leta hoon", action: { kind: "end" } },
      ],
    },
    win: {
      id: "win",
      message:
        "Wah bhai wah! 🔥 Solid kaam.\n\nLekin ek senior bhai ki advice — ek green day ek system nahi banata. 3 things abhi kar:\n1. Profit ka 30% withdraw kar account se. Wo paisa apna hai. 💰\n2. Position size mat badha — same rules continue\n3. Journal mein likh: kya kaam aaya, repeat karna hai\n\nDiscipline > excitement.",
      options: [
        { label: "Trades export karu", action: { kind: "open_url", url: "/trades" } },
        { label: "Done, thanks bhai", action: { kind: "end" } },
      ],
    },
    burnout: {
      id: "burnout",
      message:
        "Bhai burnout real hai aur ignore karna mehnga padta hai.\n\nAbhi 3 din ka break le. Sab strategies pause kar de. Family time, gym, sleep — back to basics.\n\nMarket bhaagega nahi. 15 saal baad bhi rahega. Tu rahega toh hi cricket khelega.",
      options: [
        { label: "Strategies pause karu", action: { kind: "open_url", url: "/strategies" } },
        { label: "Founder se long talk", action: { kind: "escalate", channel: "calendly" } },
      ],
    },
    confused: {
      id: "confused",
      message:
        "Confusion normal hai bhai — 7 brokers, 50+ instruments, infinite strategies. Sab ek saath samjhna possible nahi.\n\nLet's simplify — ek priority pick kar:",
      options: [
        { label: "Setup help chahiye", action: { kind: "switch_flow", flowId: "setup" } },
        { label: "Basics seekhne hain", action: { kind: "switch_flow", flowId: "education" } },
        { label: "Founder se 1-on-1", action: { kind: "escalate", channel: "calendly" } },
      ],
    },
  },
};

// ═══════════════════════════════════════════════════════════════════════
// Registry
// ═══════════════════════════════════════════════════════════════════════

export const FLOWS: Record<FlowId, Flow> = {
  welcome: welcomeFlow,
  setup: setupFlow,
  error: errorFlow,
  education: educationFlow,
  support: supportFlow,
};

export const FLOW_LIST: readonly { id: FlowId; name: string; emoji: string; tagline: string }[] = [
  { id: "welcome", name: "Get Started", emoji: "👋", tagline: "Naya hoon yahan" },
  { id: "setup", name: "Broker Setup", emoji: "🔌", tagline: "Connection mein help" },
  { id: "error", name: "Fix Errors", emoji: "🛠️", tagline: "Order / webhook issue" },
  { id: "education", name: "Learn", emoji: "📚", tagline: "Risk + strategy basics" },
  { id: "support", name: "Vent / Talk", emoji: "🤝", tagline: "Loss day / burnout" },
];
