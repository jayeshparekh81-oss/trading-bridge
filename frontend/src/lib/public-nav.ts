/**
 * The public site's nav and footer — the shop window (founder, 2026-09-05):
 * Home · Proof · Pricing in the header; About/Contact live in the footer.
 * Old URLs (/about, /contact, /home#features) keep resolving.
 */
export const PUBLIC_NAV = [
  { label: "Home", href: "/home" },
  { label: "Proof", href: "/showcase" },
  { label: "Pricing", href: "/pricing" },
] as const;

export const PUBLIC_FOOTER_COLS = [
  {
    title: "Product",
    links: [
      { label: "Home", href: "/home" },
      { label: "Proof", href: "/showcase" },
      { label: "Pricing", href: "/pricing" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms", href: "/terms" },
      { label: "Privacy", href: "/privacy" },
      { label: "Disclaimer", href: "/disclaimer" },
      { label: "SEBI Info", href: "/sebi" },
    ],
  },
] as const;
