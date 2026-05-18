import type { TutorialScript } from "./_types";

export const DHAN_CONNECT: TutorialScript = {
  topic: "dhan-connect",
  duration_target_seconds: 270,

  hindi_script: {
    intro:
      "Namaste, Jayesh wapas hu. Aaj main aapko dikhata hu ki TradeTri se Dhan broker kaise connect karte hain. Dhan tezi se popular ho raha hai retail traders mein — F&O charges low hain aur API stable hai. Process 2 minute lagta hai.",
    sections: [
      {
        time_start: 12,
        time_end: 60,
        narration:
          "Pehle TradeTri dashboard pe login karein. Left sidebar mein 'Brokers' tab pe click karein. Aapko 5 brokers ki list dikhegi — Zerodha, Dhan, Upstox, ICICI, Angel One. Dhan ke 'Connect' button pe click karein. Naya tab khulega Dhan ke OAuth page pe.",
        screen_action:
          "Logged-in dashboard. Click 'Brokers' in left sidebar. Brokers page loads. Cursor moves to Dhan card, clicks 'Connect'. New browser tab opens with Dhan login page.",
        b_roll_suggested:
          "Logos of all 5 brokers in a strip, with Dhan logo briefly highlighted",
      },
      {
        time_start: 60,
        time_end: 130,
        narration:
          "Dhan ke account credentials se login karein. Agar 2FA hai to OTP daalein. Phir Dhan poochhega 'TradeTri ko ye permissions de raha hu' — read, place orders, view P&L. IMPORTANT: ye permissions read-only nahi hain — order placement bhi included hai. Lekin TradeTri kabhi bhi aapke paise withdraw nahi kar sakta. Funds Dhan ke paas hi rehte.",
        screen_action:
          "Dhan login form. Email + password entered. 2FA OTP screen, OTP entered. OAuth consent screen showing 'TradeTri requests: read positions, place orders, view P&L'. Permissions list highlighted with annotated callouts.",
        b_roll_suggested:
          "Annotated diagram showing: User → Permission Grant → TradeTri → Order to Dhan → Dhan executes. Money flow shown as 'Dhan only' loop.",
      },
      {
        time_start: 130,
        time_end: 200,
        narration:
          "'Authorize' click karein. TradeTri tab pe wapas redirect ho jaayega. Connection success message dikhega — green tick ke saath. Ab aapka Dhan account TradeTri se linked hai. Daily session token rotate karna padta hai — Dhan ka API rule hai, har subah aapko reauthorize karna padega. Hum reminder bhejte hain T-12 hours pehle.",
        screen_action:
          "Click 'Authorize'. Brief loading state. Redirect to TradeTri dashboard. Green checkmark animation. 'Dhan Connected' badge appears on the broker card. Daily-rotation reminder banner.",
        b_roll_suggested:
          "Calendar animation showing daily rotation pattern, T-12h email/SMS reminder mock-up",
      },
      {
        time_start: 200,
        time_end: 250,
        narration:
          "Ek baar connect hua, to live trading switch enable ho jaayega — but use abhi mat karein. Pehle paper-trade karein at least 4 hafte. Live July 2026 mein open hota hai vetted accounts ke liye. Disconnect karna ho to Brokers page pe 'Revoke' click karein — Dhan side se bhi revoke kar sakte ho, koi penalty nahi.",
        screen_action:
          "Broker card now shows 'Connected' status. Live-trading toggle visible but greyed out with 'Available July 2026' label. Cursor hovers on Revoke button (without clicking).",
        b_roll_suggested:
          "Quick calendar tear-off showing July 2026 highlighted, then a 4-week paper-trading countdown visual",
      },
    ],
    outro:
      "Yahi process Zerodha, Upstox, ICICI, Angel One ke liye bhi same hai — sirf OAuth screen alag dikhta. Koi issue aaye to support ko reply karein, ya AlgoMitra se puchein. Subscribe karein — agla tutorial pehli strategy template clone karne pe hai.",
    total_word_count: 320,
  },

  english_script: {
    intro:
      "Hi, Jayesh back. Today I'm showing you how to connect Dhan broker to TradeTri. Dhan is gaining popularity with retail traders fast — low F&O charges and a stable API. The process takes 2 minutes.",
    sections: [
      {
        time_start: 11,
        time_end: 58,
        narration:
          "First, log in to your TradeTri dashboard. Click 'Brokers' in the left sidebar. You'll see five brokers — Zerodha, Dhan, Upstox, ICICI, Angel One. Click 'Connect' on the Dhan card. A new tab opens with Dhan's OAuth login page.",
        screen_action:
          "Dashboard. Click 'Brokers' in sidebar. Brokers page. Click 'Connect' on Dhan card. New tab opens.",
        b_roll_suggested: "Strip of broker logos, Dhan briefly highlighted",
      },
      {
        time_start: 58,
        time_end: 128,
        narration:
          "Log in with your Dhan credentials. If you have 2FA, enter the OTP. Then Dhan asks: 'You're giving TradeTri these permissions' — read positions, place orders, view P&L. Important: these permissions include order placement, not just read. But TradeTri can NEVER withdraw money from your Dhan account. Funds stay with Dhan, full stop.",
        screen_action:
          "Dhan login form. Email + password. OTP screen, OTP entered. OAuth consent page with permission list annotated.",
        b_roll_suggested:
          "Annotated diagram: User → Permission → TradeTri → Order → Dhan executes. Money stays at Dhan.",
      },
      {
        time_start: 128,
        time_end: 198,
        narration:
          "Click 'Authorize'. You're redirected back to TradeTri. Connection success message with a green tick. Your Dhan account is now linked. Note: Dhan requires daily session-token rotation — every morning you'll need to reauthorize. We send a reminder 12 hours before expiry so you're never caught off-guard.",
        screen_action:
          "Click Authorize. Loading. Redirect to TradeTri dashboard. Green checkmark animation. 'Dhan Connected' badge. Daily-rotation banner.",
        b_roll_suggested: "Calendar animation showing daily rotation cycle",
      },
      {
        time_start: 198,
        time_end: 248,
        narration:
          "Once connected, the live trading switch is enabled — but don't flip it yet. Paper-trade for at least 4 weeks first. Live opens for vetted accounts in July 2026. To disconnect, click 'Revoke' on the Brokers page — or revoke from Dhan side. No penalty either way.",
        screen_action:
          "Card shows 'Connected'. Live toggle visible, greyed with 'July 2026' label. Cursor hovers Revoke without clicking.",
        b_roll_suggested: "Calendar showing July 2026 highlighted",
      },
    ],
    outro:
      "Same process works for Zerodha, Upstox, ICICI, and Angel One — only the OAuth screen looks different. Any issues, reply to support or ask AlgoMitra. Subscribe — next tutorial is cloning your first strategy template.",
    total_word_count: 305,
  },

  thumbnail_text_options: [
    "Connect Dhan in 2 mins",
    "Broker → TradeTri OAuth",
    "Dhan Connect — Safe & Reversible",
  ],
  hashtags: [
    "#TradeTri",
    "#DhanHQ",
    "#BrokerConnect",
    "#NSEFO",
    "#IndianRetailTraders",
    "#AlgoTrading",
  ],
  target_audience: "New TradeTri users who use Dhan and want to wire it up",
  prerequisites: [
    "Active Dhan account",
    "Dhan 2FA enabled (recommended)",
    "TradeTri account already created",
  ],
};
