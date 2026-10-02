/**
 * Language markers for the one-language-per-screen guard (founder, 2 Oct 2026, item 5).
 *
 * HINGLISH_MARKERS: words that occur in the product's Hinglish and never in plain English prose.
 * Chosen so that an English sentence cannot trip them (no "me", "par", "se", "band", "din", "ya" —
 * each is also an English word or a name). A hit in an ENGLISH render = a Hinglish string leaked.
 *
 * ENGLISH_ONLY_MARKERS: English function-word patterns that Hinglish never uses as a sentence
 * frame. A Hinglish sentence freely borrows English NOUNS ("signal", "practice", "broker") — those
 * are its voice — so the English markers are frames, not nouns: a hit in a HINGLISH render means a
 * whole English sentence leaked, not a borrowed word.
 *
 * Both lists are judged on rendered TEXT, never on code. Product and brand names, language names,
 * tickers and legal terms are allowed in every language (ALLOWED_ANYWHERE).
 */

export const HINGLISH_MARKERS: RegExp =
  /\b(karo|karein|karna|karte|karta|karti|karunga|karenge|nahi|nahin|chuno|jodo|abhi|aapka|aapke|aapki|kya|kaise|kadam|chalu|nakli|asli|paisa|paise|bhasha|seekho|seekhne|hoga|hogi|honge|sakte|sakta|sakti|lagta|lagti|lagega|lagenge|baad|pehle|phir|kuch|wala|wali|wale|batao|batata|samjho|dikhte|dikhta|dikhti|dikhega|dikhegi|baaki|zaroori|galat|sahi|theek|madad|ghar|khata|khuli|khula|khule|hua|hui|gaya|gayi|gaye|liye|jaise|matlab|aaj|kabhi|intezaar|jaanch|rasid|dukaan|bhi|aur|hain|hai|yeh|woh|toh|kholo|dabao|dekho|banao|chahiye|raha|rahi|rahe|rehta|rehti|lekin|sirf|zyada|roz|hamesha|saath|bina|apna|apne|apni|hamara|hamare|mera|meri|mere|kaun|kahan|kyun|kyunki|isliye|warna|jaldi|shuru|khatam|poora|poori|naya|nayi|naye|purana|purani|purane|chhota|haan|bhejo|bhejte|likho|padho|wapas|neeche|upar|yahan|wahan|yahin|dobara|thoda|thodi|bahut|aasan|mushkil|tay|hisaab|daam|nuksaan|faisla|salah|vaada|vaade|niyam|bharosa|imaandaar|imaandaari|jude|juda|jodna|banane|banaya|bani|bana|chalta|chalti|chalegi|chalao|roko|ruko|sabse|kitna|kitni|kitne|jitna|utna|aage|peeche|andar|bahar|dikhao|chhupao|mitega)\b/i;

export const ENGLISH_ONLY_MARKERS: RegExp[] = [
  /\b(the|this|that|these|those) [a-z]+ (is|are|was|were|will|can|cannot|has|have|does|do)\b/i,
  /\b(you|we|they) (can|cannot|will|are|were|have|need|see|choose|pick|connect|start|stop)\b/i,
  /\byour (own|account|broker|money|strategy|choice|language)\b/i,
  /\b(please|click|tap) (here|below|the|to)\b/i,
  /\bno (real|new|signal|trade|order) [a-z]+ (yet|today|has|was|is)\b/i,
];

/**
 * Words allowed in every language: names and terms, never translated. A marker hit INSIDE one of
 * these is not a leak. (Checked by removing them from the text before the marker scan.)
 */
export const ALLOWED_ANYWHERE: RegExp[] = [
  /TRADETRI/g,
  /AlgoMitra/g,
  /Hinglish|English|हिन्दी|ગુજરાતી|Hindi|Gujarati/g,
  /Dhan|Fyers|Zerodha|Upstox|AngelOne|Shoonya|Razorpay|TradingView|WhatsApp|Telegram/g,
  /NOT MEASURED/g,
  /SEBI|NSE|BSE|F&O|SHA-256|CSV|L&T|Atal Setu|Vadodara|Mumbai|Gujarat|India/g,
  /\bRs\b|₹/g,
];

export function stripAllowed(text: string): string {
  let t = text;
  for (const re of ALLOWED_ANYWHERE) t = t.replace(re, " ");
  return t;
}

export function hinglishLeaks(text: string): string[] {
  const t = stripAllowed(text);
  const hits: string[] = [];
  // report the WORDS that tripped, de-duplicated, for a readable failure
  const re = new RegExp(HINGLISH_MARKERS.source, "gi");
  let m: RegExpExecArray | null;
  while ((m = re.exec(t))) {
    const w = m[0].toLowerCase();
    if (!hits.includes(w)) hits.push(w);
  }
  return hits;
}

export function englishLeaks(text: string): string[] {
  const t = stripAllowed(text);
  return ENGLISH_ONLY_MARKERS.map((re) => t.match(re)?.[0]).filter((x): x is string => !!x);
}
