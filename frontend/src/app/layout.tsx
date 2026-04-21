import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "TRADETRI \u2014 India's AI-Powered Algo Trading Platform",
  description:
    "Trade smarter with AI. Connect 6 brokers, run 200+ strategies, and automate your trading. Built by L&T engineer. Made for India.",
  openGraph: {
    title: "TRADETRI \u2014 India's AI-Powered Algo Trading Platform",
    description:
      "Trade smarter with AI. Connect 6 brokers, run 200+ strategies, and automate your trading. Built by L&T engineer. Made for India.",
    type: "website",
    url: "https://thetradedeskai.com",
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
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
