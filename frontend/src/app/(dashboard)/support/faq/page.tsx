/**
 * /support/faq — RETIRED. Redirects to /help.
 *
 * This page held a legacy 23-question Hinglish FAQ that duplicated the
 * bilingual help centre. Having two FAQs meant two places to keep true, and
 * only one of them was in the navigation. The eight questions that had no
 * equivalent in /help were carried across (see faq-content.ts), so nothing was
 * lost — this route now just forwards, keeping any existing bookmark working.
 */

import { redirect } from "next/navigation";

export default function SupportFaqRedirect() {
  redirect("/help");
}
