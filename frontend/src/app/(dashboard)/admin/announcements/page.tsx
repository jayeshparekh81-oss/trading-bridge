"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Megaphone, Send, Mail, MessageSquare, Bell, Clock, Users, Eye } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { adminMockData } from "@/lib/admin-mock-data";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function AnnouncementsPage() {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [target, setTarget] = useState("all");
  const [channels, setChannels] = useState({ email: true, telegram: true, inApp: true });

  const toggleChannel = (ch: keyof typeof channels) =>
    setChannels((prev) => ({ ...prev, [ch]: !prev[ch] }));

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="h-6 w-6 text-accent-purple" /> Announcements
        </h1>
        <p className="text-muted-foreground text-sm mt-1">Send notifications to your users</p>
      </motion.div>

      {/* Compose */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">New Announcement</h2>
          <div className="space-y-4">
            {/* Target */}
            <div>
              <label className="text-sm font-medium text-muted-foreground">Send To</label>
              <select value={target} onChange={(e) => setTarget(e.target.value)} className="w-full h-9 px-3 mt-1 rounded-lg bg-muted/50 border border-border text-sm">
                <option value="all">All Users ({adminMockData.activeUsers})</option>
                <option value="pro">Pro Users</option>
                <option value="basic">Basic Users</option>
                <option value="free">Free Users</option>
              </select>
            </div>

            {/* Channels */}
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-2 block">Channels</label>
              <div className="flex gap-3">
                {[
                  { key: "email" as const, label: "Email", icon: Mail },
                  { key: "telegram" as const, label: "Telegram", icon: MessageSquare },
                  { key: "inApp" as const, label: "In-App", icon: Bell },
                ].map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => toggleChannel(key)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm",
                      channels[key] ? "border-accent-purple/40 bg-accent-purple/10 text-accent-purple" : "border-border text-muted-foreground hover:bg-accent"
                    )}
                  >
                    <Icon className="h-4 w-4" />{label}
                  </button>
                ))}
              </div>
            </div>

            {/* Subject */}
            <div>
              <label className="text-sm font-medium text-muted-foreground">Subject</label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Announcement subject..." className="mt-1" />
            </div>

            {/* Message */}
            <div>
              <label className="text-sm font-medium text-muted-foreground">Message</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Write your announcement..."
                rows={6}
                className="w-full mt-1 px-3 py-2 rounded-lg bg-muted/50 border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <Dialog>
                <DialogTrigger>
                  <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm">
                    <Eye className="h-4 w-4" />Preview
                  </button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Preview Announcement</DialogTitle></DialogHeader>
                  <div className="space-y-3 pt-4">
                    <div className="text-sm"><span className="text-muted-foreground">Subject: </span><span className="font-medium">{subject || "(no subject)"}</span></div>
                    <div className="text-sm"><span className="text-muted-foreground">To: </span>{target === "all" ? "All Users" : `${target} Users`}</div>
                    <div className="p-4 rounded-lg bg-white/[0.03] border border-white/[0.04] text-sm whitespace-pre-wrap">{message || "(no message)"}</div>
                  </div>
                </DialogContent>
              </Dialog>

              <Dialog>
                <DialogTrigger>
                  <GlowButton disabled={!subject || !message}>
                    <Send className="h-4 w-4 mr-2" />
                    Send to {target === "all" ? adminMockData.activeUsers : "—"} users
                  </GlowButton>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Confirm Send</DialogTitle></DialogHeader>
                  <p className="text-sm text-muted-foreground py-2">
                    Send &quot;{subject}&quot; to {target === "all" ? adminMockData.activeUsers : "selected"} users via{" "}
                    {Object.entries(channels).filter(([, v]) => v).map(([k]) => k).join(", ")}?
                  </p>
                  <GlowButton className="w-full"><Send className="h-4 w-4 mr-2" />Confirm Send</GlowButton>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Past Announcements */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Past Announcements</h2>
          <div className="space-y-3">
            {adminMockData.announcements.map((ann) => (
              <div key={ann.id} className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-medium">{ann.subject}</div>
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{ann.message}</p>
                  </div>
                  <Badge variant="outline" className="text-xs shrink-0 ml-4">
                    <Users className="h-3 w-3 mr-1" />{ann.sentTo} sent
                  </Badge>
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(ann.sentAt).toLocaleDateString("en-IN")}</span>
                  <span>via {ann.channels.join(", ")}</span>
                </div>
              </div>
            ))}
          </div>
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}
