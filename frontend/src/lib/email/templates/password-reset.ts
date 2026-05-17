import type { EmailTemplate } from "./_types";

export const PASSWORD_RESET: EmailTemplate = {
  slug: "password-reset",
  name: "Password reset request",
  category: "transactional",

  subject_en: "Reset your TradeTri password",
  subject_hi: "Apna TradeTri password reset karein",

  body_en: `Hi {{user_name}},

We received a request to reset the password for your TradeTri account ({{user_email}}).

If you made this request, click below to set a new password. This link expires in 60 minutes.

{{reset_url}}

If you DID NOT request this, ignore this email — your account is safe and your current password still works. We'd recommend enabling 2FA from the Security tab as an extra precaution.

For account security, TradeTri will never ask for your password over email, SMS, or phone. We will never ask for your broker API secret either — those stay encrypted on our servers and even our support team cannot read them.

— Team TradeTri Security
{{support_email}}
`,
  body_hi: `Namaste {{user_name}},

Hum ne aapke TradeTri account ({{user_email}}) ke password reset ka request receive kiya.

Agar ye request aap ne ki to neeche click karke naya password set karein. Link 60 minutes mein expire ho jaayega.

{{reset_url}}

Agar ye request aap ne NAHI ki to is email ko ignore karein — aapka account safe hai aur current password kaam karta rahega. Extra precaution ke liye Security tab se 2FA enable karna recommend karte hain.

Account security ke liye, TradeTri kabhi bhi email, SMS, ya phone pe password nahi maangega. Broker API secret bhi nahi maangega — wo encrypted hamare servers pe rahta hai aur hamari support team bhi nahi padh sakti.

— Team TradeTri Security
{{support_email}}
`,

  required_vars: ["user_name", "user_email", "reset_url", "support_email"],
};
