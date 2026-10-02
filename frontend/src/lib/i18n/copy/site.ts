/**
 * Site-wide words: the practice banner (the honest line, identical in weight in both voices),
 * the signup-closed lines, the public top bar / footer, the shared signup-or-login link.
 */

import { defineCopy } from "@/lib/i18n/core";

export const siteCopy = defineCopy("site", {
  en: {
    // THE HONEST LINE — same facts, same weight as the Hinglish one (founder, item 6: nothing softened).
    practice_line: "Practice mode: on this path orders are dummy — no real money is used and no order reaches a broker.",
    signup_closed: "New accounts are closed for now — opening soon.",
    signup_invite_only:
      "New accounts are invite-only for now. Use the email that was invited — no account is created for any other email.",
    login: "Log in",
    open_app: "Open the app",
    start_free: "Start (free)",
    start_free_closed: "Log in (new accounts closed for now)",
    signup_closed_short: "New accounts closed for now",
    menu: "Menu",
    footer_tagline: "Every signal, every fill — shown. Built in India.",
    footer_made: "Made in India",
    nav_home: "Home",
    nav_proof: "Proof",
    nav_pricing: "Pricing",
    nav_about: "About",
    nav_contact: "Contact",
    col_product: "Product",
    col_company: "Company",
    col_legal: "Legal",
    legal_terms: "Terms",
    legal_privacy: "Privacy",
    legal_disclaimer: "Disclaimer",
    legal_sebi: "SEBI info",
    toast_logged_in: "Logged in",
    toast_registered: "Account created — taking you in…",
    toast_logged_out: "You are logged out",
  },
  hinglish: {
    practice_line: "Practice mode: is raaste par nakli order hote hain, asli paisa nahi lagta — koi order broker tak nahi jaata.",
    signup_closed: "Abhi naye account band hain — jaldi khulenge.",
    signup_invite_only:
      "Abhi naye account sirf invite se bante hain. Invite wala email hi daaliye — baaki email par account nahi banega.",
    login: "Login karo",
    open_app: "App kholo",
    start_free: "Shuru karo (free)",
    start_free_closed: "Login karo (naye account abhi band)",
    signup_closed_short: "Naye account abhi band",
    menu: "Menu",
    footer_tagline: "Har signal, har bhara order — saaf dikhaya. India me banaya.",
    footer_made: "India me banaya",
    nav_home: "Ghar",
    nav_proof: "Proof",
    nav_pricing: "Daam",
    nav_about: "Hamare baare me",
    nav_contact: "Hume likho",
    col_product: "Product",
    col_company: "Company",
    col_legal: "Kanooni",
    legal_terms: "Shartein",
    legal_privacy: "Privacy",
    legal_disclaimer: "Disclaimer",
    legal_sebi: "SEBI jaankari",
    toast_logged_in: "Login ho gaya",
    toast_registered: "Account ban gaya — ab aapko andar le ja rahe hain…",
    toast_logged_out: "Aap bahar aa gaye (logout)",
  },
});
