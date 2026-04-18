/* Admin panel mock data */

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  plan: "free" | "basic" | "pro";
  status: "active" | "trial" | "locked" | "inactive";
  isAdmin: boolean;
  totalTrades: number;
  totalPnl: number;
  winRate: number;
  brokersConnected: number;
  lastLogin: string;
  lastIp: string;
  createdAt: string;
}

export interface AuditLogEntry {
  id: string;
  time: string;
  actor: "system" | "user" | "admin";
  actorName: string;
  action: string;
  resource: string;
  resourceId: string;
  ip: string;
  metadata: Record<string, unknown>;
}

export interface AdminKillSwitchEvent {
  id: string;
  triggeredAt: string;
  userName: string;
  userId: string;
  reason: string;
  dailyPnl: number;
  positionsClosed: number;
  squareOffTime: number;
  resetAt: string | null;
  resetBy: string | null;
}

export interface Announcement {
  id: string;
  subject: string;
  message: string;
  sentAt: string;
  sentTo: number;
  channels: string[];
}

export interface AdminDashboardData {
  activeUsers: number;
  ordersToday: number;
  avgLatencyMs: number;
  revenueMonth: number;
  killSwitchTrips: number;
  errorRate: number;
  systemStatus: "healthy" | "degraded" | "down";
  requestsPerMinute: { time: string; rpm: number }[];
  brokerHealth: { name: string; status: "online" | "degraded" | "offline" | "not_deployed"; latencyMs: number; successRate: number }[];
  recentAlerts: { id: string; time: string; severity: "info" | "warning" | "critical"; message: string }[];
  users: AdminUser[];
  auditLogs: AuditLogEntry[];
  killSwitchEvents: AdminKillSwitchEvent[];
  announcements: Announcement[];
}

export const adminMockData: AdminDashboardData = {
  activeUsers: 156,
  ordersToday: 1247,
  avgLatencyMs: 42,
  revenueMonth: 240000,
  killSwitchTrips: 2,
  errorRate: 0.3,
  systemStatus: "healthy",
  requestsPerMinute: Array.from({ length: 60 }, (_, i) => ({
    time: `${String(Math.floor(i / 60) + 9).padStart(2, "0")}:${String(i % 60).padStart(2, "0")}`,
    rpm: Math.floor(80 + Math.random() * 120),
  })),
  brokerHealth: [
    { name: "Fyers", status: "online", latencyMs: 35, successRate: 99.9 },
    { name: "Dhan", status: "online", latencyMs: 28, successRate: 99.8 },
    { name: "Shoonya", status: "not_deployed", latencyMs: 0, successRate: 0 },
    { name: "Zerodha", status: "not_deployed", latencyMs: 0, successRate: 0 },
  ],
  recentAlerts: [
    { id: "a1", time: "2026-04-17T10:15:00+05:30", severity: "critical", message: "Kill Switch tripped for user Rahul S. (daily loss -\u20B95,234)" },
    { id: "a2", time: "2026-04-17T09:30:00+05:30", severity: "warning", message: "Fyers latency spike to 180ms (normally 35ms)" },
    { id: "a3", time: "2026-04-17T09:15:00+05:30", severity: "warning", message: "3 failed login attempts from IP 103.21.58.xx" },
    { id: "a4", time: "2026-04-17T09:00:00+05:30", severity: "info", message: "Daily P&L reset completed for all 156 users" },
    { id: "a5", time: "2026-04-16T15:15:00+05:30", severity: "info", message: "Auto square-off executed for 23 users (3:15 PM IST)" },
  ],
  users: [
    { id: "u1", name: "Jayesh Parekh", email: "jayesh@thetradedeskai.com", plan: "pro", status: "active", isAdmin: true, totalTrades: 325, totalPnl: 120000, winRate: 72, brokersConnected: 2, lastLogin: "2026-04-17T08:00:00+05:30", lastIp: "103.21.58.101", createdAt: "2026-03-01" },
    { id: "u2", name: "Rahul Sharma", email: "rahul@gmail.com", plan: "pro", status: "active", isAdmin: false, totalTrades: 180, totalPnl: 65000, winRate: 68, brokersConnected: 1, lastLogin: "2026-04-17T09:15:00+05:30", lastIp: "182.73.12.45", createdAt: "2026-03-10" },
    { id: "u3", name: "Priya Mehta", email: "priya@outlook.com", plan: "free", status: "trial", isAdmin: false, totalTrades: 45, totalPnl: 8500, winRate: 60, brokersConnected: 1, lastLogin: "2026-04-16T14:00:00+05:30", lastIp: "49.36.78.22", createdAt: "2026-04-01" },
    { id: "u4", name: "Amit Kumar", email: "amit@yahoo.com", plan: "pro", status: "locked", isAdmin: false, totalTrades: 520, totalPnl: -12000, winRate: 45, brokersConnected: 2, lastLogin: "2026-04-15T10:00:00+05:30", lastIp: "122.176.45.89", createdAt: "2026-03-05" },
    { id: "u5", name: "Sneha Patel", email: "sneha@gmail.com", plan: "basic", status: "active", isAdmin: false, totalTrades: 90, totalPnl: 22000, winRate: 71, brokersConnected: 1, lastLogin: "2026-04-17T08:30:00+05:30", lastIp: "203.192.11.67", createdAt: "2026-03-15" },
    { id: "u6", name: "Vikram Singh", email: "vikram@hotmail.com", plan: "basic", status: "inactive", isAdmin: false, totalTrades: 20, totalPnl: -3000, winRate: 40, brokersConnected: 0, lastLogin: "2026-04-10T12:00:00+05:30", lastIp: "59.95.123.45", createdAt: "2026-03-20" },
  ],
  auditLogs: [
    { id: "al1", time: "2026-04-17T10:15:03+05:30", actor: "system", actorName: "System", action: "kill_switch_triggered", resource: "user", resourceId: "u2", ip: "", metadata: { reason: "daily_loss", pnl: -5234 } },
    { id: "al2", time: "2026-04-17T10:14:58+05:30", actor: "user", actorName: "Rahul S.", action: "place_order", resource: "trade", resourceId: "t891", ip: "182.73.12.45", metadata: { symbol: "NIFTY CE", side: "BUY", qty: 50 } },
    { id: "al3", time: "2026-04-17T10:14:55+05:30", actor: "system", actorName: "System", action: "webhook_received", resource: "webhook", resourceId: "w234", ip: "52.89.214.238", metadata: { signal: "BUY NIFTY" } },
    { id: "al4", time: "2026-04-17T09:30:01+05:30", actor: "admin", actorName: "Jayesh P.", action: "user_created", resource: "user", resourceId: "u156", ip: "103.21.58.101", metadata: { email: "newuser@test.com", plan: "basic" } },
    { id: "al5", time: "2026-04-17T09:15:22+05:30", actor: "system", actorName: "System", action: "login_failed", resource: "auth", resourceId: "", ip: "1.2.3.4", metadata: { email: "unknown@test.com", attempt: 3 } },
    { id: "al6", time: "2026-04-17T09:00:00+05:30", actor: "system", actorName: "System", action: "daily_reset", resource: "kill_switch", resourceId: "", ip: "", metadata: { users_reset: 156 } },
    { id: "al7", time: "2026-04-16T15:15:00+05:30", actor: "system", actorName: "System", action: "auto_square_off", resource: "positions", resourceId: "", ip: "", metadata: { users: 23, positions: 67 } },
    { id: "al8", time: "2026-04-16T14:45:00+05:30", actor: "admin", actorName: "Jayesh P.", action: "reset_kill_switch", resource: "user", resourceId: "u4", ip: "103.21.58.101", metadata: { reason: "customer request" } },
  ],
  killSwitchEvents: [
    { id: "kse1", triggeredAt: "2026-04-17T10:15:00+05:30", userName: "Rahul Sharma", userId: "u2", reason: "Daily loss exceeded \u20B95,000", dailyPnl: -5234, positionsClosed: 3, squareOffTime: 1200, resetAt: null, resetBy: null },
    { id: "kse2", triggeredAt: "2026-04-16T14:20:00+05:30", userName: "Amit Kumar", userId: "u4", reason: "Daily loss exceeded \u20B98,000", dailyPnl: -8100, positionsClosed: 5, squareOffTime: 1800, resetAt: "2026-04-16T14:45:00+05:30", resetBy: "Jayesh P. (Admin)" },
    { id: "kse3", triggeredAt: "2026-04-15T11:05:00+05:30", userName: "Priya Mehta", userId: "u3", reason: "Max daily trades reached (50/50)", dailyPnl: -3500, positionsClosed: 2, squareOffTime: 850, resetAt: "2026-04-15T12:00:00+05:30", resetBy: "Auto (next day)" },
  ],
  announcements: [
    { id: "ann1", subject: "New feature: Kill Switch!", message: "We've launched per-user kill switch with auto square-off...", sentAt: "2026-04-15T10:00:00+05:30", sentTo: 156, channels: ["email", "telegram"] },
    { id: "ann2", subject: "Welcome to TradeDesk AI Beta!", message: "Thank you for joining our beta program...", sentAt: "2026-04-10T09:00:00+05:30", sentTo: 50, channels: ["email"] },
  ],
};
