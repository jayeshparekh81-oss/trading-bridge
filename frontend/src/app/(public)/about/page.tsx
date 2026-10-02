"use client";

import { motion } from "framer-motion";
import { Building2, Landmark, Eye, ShieldCheck, Wallet, LineChart, ArrowRight } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { Logo } from "@/components/logo";
import Link from "next/link";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function AboutPage() {
  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Hero */}
        <motion.div variants={fadeUp} className="text-center">
          <div className="flex items-center justify-center gap-2 mb-6">
            <Logo variant="icon" width={44} height={44} priority />
            <Logo variant="wordmark" height={40} />
          </div>
          <p className="text-xs font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
            Har signal, saaf dikhega
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-[1.1]">
            Ek{" "}
            <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
              engineer
            </span>{" "}
            ne banaya, influencer ne nahi.
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mt-5 leading-relaxed">
            TRADETRI ko L&amp;T ke ek purane engineer ne banaya hai — 24 saal ka engineering anubhav: pul, bijli ghar aur aisa dhancha jin par lakhon log bharosa karte hain — ab algo trading me, jo har signal uske daam, stop aur target ke saath dikhati hai. Vadodara, India se.
          </p>
        </motion.div>

        {/* Founder */}
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="flex flex-col md:flex-row gap-8 items-center">
              <div className="h-32 w-32 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-5xl font-bold text-white shrink-0">JP</div>
              <div>
                <h2 className="text-2xl font-bold mb-2">Jayesh Parekh</h2>
                <p className="text-accent-blue font-medium mb-4">Founder aur Engineer · Pehle L&amp;T me · 24 saal</p>
                <div className="space-y-3 text-muted-foreground">
                  <p>
                    24 saal maine L&amp;T me pul, bijli ghar aur udyog ka dhancha banaya — aise kaam jahan galti ki jagah nahi thi. Wahi aadat se main software banata hoon.
                  </p>
                  <p>
                    Jab maine trading shuru ki, platform pareshan karte the: band dibbe jaise signal, bina wajah ki pechidagi, aur bas &ldquo;bharosa karo&rdquo; ki maang. Zyadatar retail trader aise signal par bharosa karte hain jo unhe tab dikhta hai jab woh chal chuka hota hai.
                  </p>
                  <p>
                    To maine wahi banaya jo main khud istemaal karna chahta tha — har signal uske daam, stop aur target ke saath, ek niyam-aadharit bharosa score (conviction score) jo aap dekh sakte ho, har signal par subscriber ki apni haan, har trade aapke apne broker se taaki paisa wahin rahe, aur record imaandaari se. Na course, na khokhle vaade — sirf aisa system jo chale, aur dikhaye ki kaise chalta hai.
                  </p>
                </div>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>

        {/* Mission */}
        <motion.div variants={fadeUp} className="text-center">
          <h2 className="text-3xl font-bold mb-4">Hamara maqsad</h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto italic">
            &ldquo;India ke retail trader ke liye algo-trading aasan banana — jo saaf auzaar upar ke 5% ke paas hain, wahi baaki 95% ko dena.&rdquo;
          </p>
        </motion.div>

        {/* Highlights — TRUE facts only */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: Building2, value: "24 saal", label: "Engineering (L&T me)", color: "text-accent-blue" },
            { icon: Landmark, value: "2", label: "Broker jude (Dhan, Fyers)", color: "text-profit" },
            { icon: Eye, value: "Har signal", label: "Dikhega, apne score ke saath", color: "text-accent-gold" },
            { icon: ShieldCheck, value: "SEBI niyam", label: "ke hisaab se (manzoori abhi baaki)", color: "text-accent-purple" },
          ].map((s) => (
            <GlassmorphismCard key={s.label} className="text-center py-6">
              <s.icon className={`h-6 w-6 mx-auto mb-2 ${s.color}`} />
              <div className="text-lg font-bold leading-tight">{s.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
            </GlassmorphismCard>
          ))}
        </motion.div>

        {/* What TRADETRI is */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">TRADETRI asal me kya hai</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: Eye, title: "Bharosa score, sirf salah", desc: "Har signal ke saath ek niyam-aadharit score (conviction score — koi deep-learning nahi) jo batata hai ki niyam kitne pakke se haan bol rahe hain. Yeh sirf salah hai — faisla aapka, score aapki jagah nahi leta." },
              { icon: Wallet, title: "Aapka broker, aapka paisa", desc: "Trade aapke apne registered broker se hota hai. TRADETRI aapka paisa kabhi nahi rakhta." },
              { icon: LineChart, title: "Imaandaar record", desc: "Purane bazaar data wale test andaaza (hypothetical) likhe jaate hain, risk return ke bagal me rehta hai, aur live nateeje jaanch ke baad hi publish hote hain." },
            ].map((f) => (
              <GlassmorphismCard key={f.title}>
                <f.icon className="h-8 w-8 text-accent-blue mb-3" />
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.desc}</p>
              </GlassmorphismCard>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link
              href="/showcase"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline"
            >
              Dekho Proof →
            </Link>
          </div>
        </motion.div>

        {/* Timeline — honest, no fabricated metrics */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">Hamara safar</h2>
          <div className="space-y-6">
            {[
              { date: "Jan 2026", title: "Soch", desc: "Band dibbe jaise, bewajah pechide trading platform se pareshan. L&T jaisi engineering aadat se apna banane ka faisla." },
              { date: "Feb 2026", title: "Dhancha", desc: "Dikhne wala bharosa score (conviction score), ek tap me sab-band switch, aur ek se zyada broker — pehle din se." },
              { date: "Mar 2026", title: "Server ka kaam", desc: "FastAPI + PostgreSQL + Redis, broker jod, aur signal ka raasta." },
              { date: "Apr 2026", title: "Screen ka kaam", desc: "Phone-first, dark-mode dashboard." },
              { date: "May 2026", title: "Shuruaat", desc: "tradetri.com par live — nakli-paise (paper) trading, asli broker jod, aur imaandaar record. Raay le rahe hain, sudhaar rahe hain." },
            ].map((item, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="h-3 w-3 rounded-full bg-accent-blue" />
                  {i < 4 && <div className="w-px flex-1 bg-border" />}
                </div>
                <div className="pb-6">
                  <span className="text-xs text-accent-blue font-medium">{item.date}</span>
                  <h3 className="font-semibold mt-0.5">{item.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Get in touch */}
        <motion.div variants={fadeUp} className="text-center">
          <GlassmorphismCard glow="blue" className="py-10">
            <h2 className="text-2xl font-bold mb-2">Sawaal ya sujhav?</h2>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">
              Raay, saath kaam ka vichaar, ya bas baat karni ho — hume likho, achha lagega.
            </p>
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit transition-all">
              Hume likho <ArrowRight className="h-4 w-4" />
            </Link>
          </GlassmorphismCard>
        </motion.div>

        {/* Honest risk disclaimer */}
        <motion.p variants={fadeUp} className="text-xs leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto text-center">
          Trading me poonji (capital) doobne ka bada risk hai. Pichhla pradarshan aage ke nateeje ki guarantee nahi deta, aur yahan kuch bhi nivesh ki salah (investment advice) nahi hai. TRADETRI pakke return ka koi daawa nahi karta. Trade aapke apne exchange-registered broker se jaate hain, SEBI ke algo-trading niyamon ke anusaar.
        </motion.p>
      </div>
    </motion.div>
  );
}
