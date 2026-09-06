import type { Metadata, Viewport } from "next";
import {
  Geist,
  Geist_Mono,
} from "next/font/google";
import {
  Inter,
  Space_Grotesk,
  Space_Mono,
  Playfair_Display,
  Plus_Jakarta_Sans,
  DM_Sans,
  Mukta,
  Noto_Sans_Gujarati,
} from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteFooter } from "@/components/compliance/SiteFooter";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

const spaceMono = Space_Mono({
  variable: "--font-space-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  display: "swap",
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  display: "swap",
});

const mukta = Mukta({
  variable: "--font-mukta",
  subsets: ["devanagari", "latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

const notoGujarati = Noto_Sans_Gujarati({
  variable: "--font-gujarati",
  subsets: ["gujarati", "latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // ``maximumScale: 5`` keeps the pinch-zoom escape hatch intact —
  // accessibility wins over the marginally-cleaner "lock the
  // initial scale" alternative. Mobile Safari respects this; the
  // chart panes that have native zoom handle their own gesture
  // capture inside their canvas.
  maximumScale: 5,
};

export const metadata: Metadata = {
  title: "TRADETRI \u2014 Every signal shown. Your broker, your funds.",
  description:
    "Algo trading through your own Dhan or Fyers account. Every signal shown with its price, stop and target. Paper-trade first, kill switch on by default, honest backtests. Built in India.",
  openGraph: {
    title: "TRADETRI \u2014 Every signal shown. Your broker, your funds.",
    description:
      "Algo trading through your own Dhan or Fyers account. Every signal shown with its price, stop and target. Paper-trade first, kill switch on by default, honest backtests. Built in India.",
    type: "website",
    url: "https://tradetri.com",
  },
};

const fontVars = [
  geistSans.variable,
  geistMono.variable,
  inter.variable,
  spaceGrotesk.variable,
  spaceMono.variable,
  playfair.variable,
  plusJakarta.variable,
  dmSans.variable,
  mukta.variable,
  notoGujarati.variable,
].join(" ");

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fontVars} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>
          {children}
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
