import type { MarketingTemplate } from "../_types";

export const REFERRAL_MESSAGE: MarketingTemplate = {
  slug: "whatsapp-referral-message",
  platform: "whatsapp",
  use_case: "Pre-written message for users to forward to friends (referral)",
  audience: "active_user",

  content_en: `Hey, I've been using TradeTri to paper-trade NSE F&O strategies for {{user_tracking_days}} days. Thought you might find it useful.

Quick what-it-is: systematic trading for retail. No code. OAuth broker integration with kill-switch protection. Paper-trading is unlimited and free. Live trading is flat ₹{{monthly_fee}}/month — no per-trade, no profit share.

I'm not getting a commission for sending this. Just sharing because I think you'd actually use it.

If you want my referral link for tracking: {{referral_url}}

If you'd rather just sign up directly: tradetri.com
`,
  content_hi: `Bhai, main TradeTri use kar raha NSE F&O paper-trading ke liye {{user_tracking_days}} din se. Lagga tujhe bhi useful ho.

Quick baat: retail ke liye systematic trading. Code nahi. OAuth broker integration kill-switch protection ke saath. Paper-trading unlimited aur free. Live trading flat ₹{{monthly_fee}}/mahina — per-trade nahi, profit share nahi.

Mujhe commission nahi mil raha is se. Bas isliye share kar raha kyunki lagta tu actually use karega.

Tracking ke liye mera referral link: {{referral_url}}

Seedha signup karna ho: tradetri.com
`,

  required_vars: ["user_tracking_days", "monthly_fee", "referral_url"],
  cta: "Sign up at {{referral_url}}",
  estimated_chars: 700,
  visuals_suggested: ["Plain forwardable text — no images so it sends fast"],
};
