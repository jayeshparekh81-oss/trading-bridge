"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Mail, MessageSquare, MapPin, Send, ExternalLink } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function ContactPage() {
  const [sent, setSent] = useState(false);

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
          {/* Contact Form */}
          <motion.div variants={fadeUp}>
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">Send a Message</h2>
              {sent ? (
                <div className="text-center py-8">
                  <div className="h-12 w-12 rounded-full bg-profit/10 text-profit flex items-center justify-center mx-auto mb-4">
                    <Send className="h-6 w-6" />
                  </div>
                  <h3 className="font-semibold text-lg mb-2">Message Sent!</h3>
                  <p className="text-sm text-muted-foreground">We&apos;ll get back to you within 24 hours.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Name</label>
                    <Input placeholder="Your name" className="mt-1" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Email</label>
                    <Input type="email" placeholder="you@example.com" className="mt-1" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Message</label>
                    <textarea
                      placeholder="How can we help?"
                      rows={5}
                      className="w-full mt-1 px-3 py-2 rounded-lg bg-muted/50 border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring/40"
                    />
                  </div>
                  <GlowButton className="w-full" onClick={() => setSent(true)}>
                    <Send className="h-4 w-4 mr-2" />Send Message
                  </GlowButton>
                </div>
              )}
            </GlassmorphismCard>
          </motion.div>

          {/* Contact Info */}
          <motion.div variants={fadeUp} className="space-y-4">
            <GlassmorphismCard className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-accent-blue/10 text-accent-blue flex items-center justify-center shrink-0">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">Email</h3>
                <p className="text-sm text-muted-foreground">support@thetradedeskai.com</p>
                <p className="text-xs text-muted-foreground mt-1">We reply within 24 hours</p>
              </div>
            </GlassmorphismCard>

            <GlassmorphismCard className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-profit/10 text-profit flex items-center justify-center shrink-0">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">WhatsApp &amp; Telegram</h3>
                <p className="text-sm text-muted-foreground">Quick support via chat</p>
                <div className="flex gap-3 mt-2">
                  <span className="inline-flex items-center gap-1 text-xs text-profit cursor-pointer hover:underline">WhatsApp <ExternalLink className="h-3 w-3" /></span>
                  <span className="inline-flex items-center gap-1 text-xs text-accent-blue cursor-pointer hover:underline">Telegram <ExternalLink className="h-3 w-3" /></span>
                </div>
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

            <GlassmorphismCard glow="blue" className="text-center py-6">
              <h3 className="font-semibold mb-2">Need Help Setting Up?</h3>
              <p className="text-sm text-muted-foreground mb-3">Check our documentation and setup guides</p>
              <Link href="/home#features" className="text-sm text-accent-blue hover:underline font-medium">
                View Documentation &rarr;
              </Link>
            </GlassmorphismCard>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}
