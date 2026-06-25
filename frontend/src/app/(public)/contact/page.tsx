"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Mail, MessageSquare, MapPin, Send, ExternalLink } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { FOUNDER_WHATSAPP_NUMBER } from "@/lib/algomitra-personality";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

// Honest, working contact channels — no backend form-submit exists, so the form
// opens the visitor's own email client (mailto) addressed to the founder.
const SUPPORT_EMAIL = "jayeshparekh81@gmail.com";
const WHATSAPP_URL = `https://wa.me/${FOUNDER_WHATSAPP_NUMBER}?text=${encodeURIComponent(
  "Hi, I have a question about TRADETRI",
)}`;

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const subject = encodeURIComponent("TRADETRI — Contact");
    const body = encodeURIComponent(
      `${message}\n\n— ${name || "TRADETRI website visitor"}${email ? ` (${email})` : ""}`,
    );
    // Opens the visitor's email client with their message prefilled — a real action.
    window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
  };

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-4xl mx-auto space-y-10">
        <motion.div variants={fadeUp} className="text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">Get in Touch</h1>
          <p className="text-lg text-muted-foreground max-w-lg mx-auto">
            Questions? Feedback? Partnership ideas? We&apos;d love to hear from you.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Contact form — opens the visitor's email client (mailto), no fake success */}
          <motion.div variants={fadeUp}>
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">Send a Message</h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Name</label>
                  <Input
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Email</label>
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Message</label>
                  <textarea
                    placeholder="How can we help?"
                    rows={5}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-muted/50 border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring/40"
                  />
                </div>
                <GlowButton className="w-full" type="submit" disabled={!message.trim()}>
                  <Send className="h-4 w-4 mr-2" />Email Us
                </GlowButton>
                <p className="text-xs text-muted-foreground text-center">
                  Opens your email app addressed to {SUPPORT_EMAIL}.
                </p>
              </form>
            </GlassmorphismCard>
          </motion.div>

          {/* Contact info — real channels only */}
          <motion.div variants={fadeUp} className="space-y-4">
            <GlassmorphismCard className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-accent-blue/10 text-accent-blue flex items-center justify-center shrink-0">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">Email</h3>
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="text-sm text-accent-blue hover:underline break-all"
                >
                  {SUPPORT_EMAIL}
                </a>
                <p className="text-xs text-muted-foreground mt-1">We&apos;ll get back to you as soon as we can.</p>
              </div>
            </GlassmorphismCard>

            <GlassmorphismCard className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-profit/10 text-profit flex items-center justify-center shrink-0">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">WhatsApp</h3>
                <p className="text-sm text-muted-foreground">Quick support via chat</p>
                <a
                  href={WHATSAPP_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-profit hover:underline mt-2"
                >
                  Message us on WhatsApp <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </GlassmorphismCard>

            <GlassmorphismCard className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-accent-purple/10 text-accent-purple flex items-center justify-center shrink-0">
                <MapPin className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">Office</h3>
                <p className="text-sm text-muted-foreground">Vadodara, Gujarat, India</p>
                <p className="text-xs text-muted-foreground mt-1">Remote-first company</p>
              </div>
            </GlassmorphismCard>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}
