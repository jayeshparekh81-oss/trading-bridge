"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Settings, User, Bell, Shield, Palette, Key, Moon, Sun, Monitor, Eye, EyeOff } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ThemePicker } from "@/components/theme-picker";
import { FontPicker } from "@/components/font-picker";
import { useCustomTheme } from "@/lib/theme-context";
import { mockDashboard } from "@/lib/mock-data";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

function Toggle({ enabled, label }: { enabled: boolean; label: string }) {
  const [on, setOn] = useState(enabled);
  return (
    <button onClick={() => setOn(!on)} className="flex items-center gap-3">
      <div className={cn("h-5 w-9 rounded-full relative transition-colors", on ? "bg-profit" : "bg-muted")}>
        <div className={cn("h-4 w-4 rounded-full bg-white absolute top-0.5 transition-all", on ? "left-4" : "left-0.5")} />
      </div>
      <span className="text-sm">{label}</span>
    </button>
  );
}

const notifEvents = [
  { key: "order_filled", label: "Order Filled", email: true, telegram: true },
  { key: "order_failed", label: "Order Failed", email: true, telegram: true },
  { key: "kill_switch", label: "Kill Switch Trip", email: true, telegram: true },
  { key: "daily_summary", label: "Daily Summary", email: true, telegram: false },
  { key: "weekly_report", label: "Weekly Report", email: true, telegram: false },
  { key: "session_expired", label: "Session Expired", email: true, telegram: true },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const d = {
    ...mockDashboard,
    user: {
      ...mockDashboard.user,
      name: user?.full_name || mockDashboard.user.name,
      email: user?.email || mockDashboard.user.email,
      phone: user?.phone || mockDashboard.user.phone,
      telegramChatId: user?.telegram_chat_id || mockDashboard.user.telegramChatId,
    },
  };
  const { mode, setMode } = useCustomTheme();
  const [showPassword, setShowPassword] = useState(false);

  return (
    <motion.div initial="hidden" animate="show" variants={{ hidden: { opacity: 0 }, show: { opacity: 1 } }} className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-accent-blue" /> Settings
        </h1>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Tabs defaultValue="profile">
          <TabsList className="grid grid-cols-5 w-full mb-6">
            <TabsTrigger value="profile" className="flex items-center gap-1.5 text-xs"><User className="h-3.5 w-3.5" />Profile</TabsTrigger>
            <TabsTrigger value="notifications" className="flex items-center gap-1.5 text-xs"><Bell className="h-3.5 w-3.5" />Notifs</TabsTrigger>
            <TabsTrigger value="security" className="flex items-center gap-1.5 text-xs"><Shield className="h-3.5 w-3.5" />Security</TabsTrigger>
            <TabsTrigger value="appearance" className="flex items-center gap-1.5 text-xs"><Palette className="h-3.5 w-3.5" />Theme</TabsTrigger>
            <TabsTrigger value="api" className="flex items-center gap-1.5 text-xs"><Key className="h-3.5 w-3.5" />API</TabsTrigger>
          </TabsList>

          {/* Profile */}
          <TabsContent value="profile">
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">Profile</h2>
              <div className="space-y-4 max-w-md">
                <div><label className="text-sm font-medium text-muted-foreground">Full Name</label><Input defaultValue={d.user.name} className="mt-1" /></div>
                <div><label className="text-sm font-medium text-muted-foreground">Email</label><Input defaultValue={d.user.email} disabled className="mt-1 opacity-60" /><p className="text-xs text-profit mt-1">Verified</p></div>
                <div><label className="text-sm font-medium text-muted-foreground">Phone</label><Input defaultValue={d.user.phone} className="mt-1" /></div>
                <div><label className="text-sm font-medium text-muted-foreground">Telegram Chat ID</label><Input defaultValue={d.user.telegramChatId} className="mt-1" /></div>
                <GlowButton size="sm">Save Changes</GlowButton>
              </div>
            </GlassmorphismCard>
          </TabsContent>

          {/* Notifications */}
          <TabsContent value="notifications">
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">Notification Preferences</h2>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-4 text-xs font-medium text-muted-foreground uppercase">Event</th>
                      <th className="text-center py-2 px-4 text-xs font-medium text-muted-foreground uppercase">Email</th>
                      <th className="text-center py-2 px-4 text-xs font-medium text-muted-foreground uppercase">Telegram</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notifEvents.map((evt) => (
                      <tr key={evt.key} className="border-b border-border/50">
                        <td className="py-3 px-4 text-sm">{evt.label}</td>
                        <td className="py-3 px-4 text-center"><Toggle enabled={evt.email} label="" /></td>
                        <td className="py-3 px-4 text-center"><Toggle enabled={evt.telegram} label="" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <GlowButton size="sm" className="mt-4">Save Preferences</GlowButton>
            </GlassmorphismCard>
          </TabsContent>

          {/* Security */}
          <TabsContent value="security">
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">Change Password</h2>
              <div className="space-y-4 max-w-md">
                <div><label className="text-sm font-medium text-muted-foreground">Current Password</label><Input type="password" className="mt-1" /></div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">New Password</label>
                  <div className="relative mt-1">
                    <Input type={showPassword ? "text" : "password"} />
                    <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-label="Toggle password">
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div><label className="text-sm font-medium text-muted-foreground">Confirm Password</label><Input type="password" className="mt-1" /></div>
                <GlowButton size="sm">Update Password</GlowButton>
              </div>
              <div className="mt-8 pt-6 border-t border-border">
                <h3 className="font-semibold mb-2">Active Sessions</h3>
                <p className="text-sm text-muted-foreground mb-3">2 active devices</p>
                <GlowButton variant="danger" size="sm">Logout All Devices</GlowButton>
              </div>
            </GlassmorphismCard>
          </TabsContent>

          {/* Appearance */}
          <TabsContent value="appearance">
            <div className="space-y-6">
              <GlassmorphismCard hover={false}>
                <h2 className="text-lg font-semibold mb-6">Appearance</h2>

                {/* Mode */}
                <div className="mb-8">
                  <label className="text-sm font-medium text-muted-foreground mb-3 block">Mode</label>
                  <div className="flex gap-3">
                    {[
                      { value: "auto" as const, label: "Auto", icon: Monitor, desc: "Follow system" },
                      { value: "dark" as const, label: "Dark", icon: Moon, desc: "" },
                      { value: "light" as const, label: "Light", icon: Sun, desc: "" },
                    ].map((m) => (
                      <button
                        key={m.value}
                        onClick={() => setMode(m.value)}
                        className={cn(
                          "flex items-center gap-2 px-4 py-3 rounded-xl border transition-all",
                          mode === m.value ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent"
                        )}
                      >
                        <m.icon className="h-4 w-4" />
                        <span className="text-sm font-medium">{m.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Theme */}
                <div className="mb-8">
                  <label className="text-sm font-medium text-muted-foreground mb-3 block">Theme (2 active, 8 coming soon)</label>
                  <ThemePicker />
                </div>

                {/* Font */}
                <div className="mb-8">
                  <label className="text-sm font-medium text-muted-foreground mb-3 block">Font Pair (6 options)</label>
                  <FontPicker />
                </div>

                {/* Language */}
                <div className="mb-8">
                  <label className="text-sm font-medium text-muted-foreground mb-2 block">Language</label>
                  <select className="h-9 px-3 rounded-lg bg-muted/50 border border-border text-sm w-48">
                    <option>English</option>
                    <option>Hindi</option>
                    <option>Gujarati</option>
                    <option>Marathi</option>
                    <option>Tamil</option>
                    <option>Telugu</option>
                    <option>Kannada</option>
                    <option>Bengali</option>
                    <option>Malayalam</option>
                    <option>Punjabi</option>
                    <option>Odia</option>
                  </select>
                </div>
              </GlassmorphismCard>

              {/* Live Preview */}
              <GlassmorphismCard hover={false}>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">Live Preview</h3>
                <div className="rounded-xl border border-border p-6 bg-card">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Today&apos;s P&amp;L</div>
                  <div className="text-3xl font-bold text-profit glow-profit mb-3">+{"\u20B9"}12,450</div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Win Rate: <span className="text-profit font-medium">80%</span></span>
                    <span>Trades: <span className="font-medium">12</span></span>
                    <span>Streak: <span className="text-accent-gold font-medium">5 days</span></span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden">
                    <div className="h-full w-3/4 rounded-full bg-gradient-to-r from-profit to-accent-blue" />
                  </div>
                </div>
              </GlassmorphismCard>
            </div>
          </TabsContent>

          {/* API Keys */}
          <TabsContent value="api">
            <GlassmorphismCard hover={false}>
              <h2 className="text-lg font-semibold mb-4">API Keys</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-muted/20 border border-border">
                  <div>
                    <code className="text-sm font-mono">tb_k_a1b2c3d4</code>
                    <p className="text-xs text-muted-foreground mt-0.5">Created: Apr 15, 2026</p>
                  </div>
                  <button className="px-3 py-1.5 rounded-lg text-xs border border-loss/30 text-loss hover:bg-loss/10 transition-colors">Revoke</button>
                </div>
              </div>
              <GlowButton size="sm" className="mt-4"><Key className="h-4 w-4 mr-2" />Generate New API Key</GlowButton>
            </GlassmorphismCard>
          </TabsContent>
        </Tabs>
      </motion.div>
    </motion.div>
  );
}
