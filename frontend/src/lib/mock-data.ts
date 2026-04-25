/* ═══════════════════════════════════════════════════════════════════════
   Mock data for ALL dashboard pages — replaced by real API in Step 14.
   ═══════════════════════════════════════════════════════════════════════ */

// ─── Shared Types ──────────────────────────────────────────────────────

export interface Trade {
  id: string;
  time: string;
  action: "BUY" | "SELL";
  symbol: string;
  quantity: number;
  price: number;
  pnl: number;
  status: "complete" | "pending" | "rejected";
  broker: string;
  strategy: string;
  latencyMs?: number;
  orderId?: string;
}

export interface Strategy {
  id: string;
  name: string;
  winRate: number;
  todayPnl: number;
  monthPnl: number;
  totalTrades: number;
  todayTrades: number;
  isActive: boolean;
  broker: string;
  webhookConnected: boolean;
}

export interface Broker {
  name: string;
  status: "connected" | "expired" | "not_connected" | "coming_soon";
  latencyMs: number;
  lastLogin: string;
  id?: string;
}

export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  broker: string;
  side: "LONG" | "SHORT";
}

export interface WebhookToken {
  id: string;
  token: string;
  hmacSecret: string;
  label: string;
  strategy: string;
  broker: string;
  isActive: boolean;
  lastUsed: string;
  created: string;
}

export interface KillSwitchEvent {
  id: string;
  triggeredAt: string;
  reason: string;
  dailyPnl: number;
  positionsClosed: number;
  resetAt: string | null;
}

export interface AnalyticsPeriod {
  winRate: number;
  totalPnl: number;
  sharpe: number;
  totalTrades: number;
  bestDay: { date: string; pnl: number };
  worstDay: { date: string; pnl: number };
  avgTradesPnl: number;
  equityCurve: { date: string; value: number }[];
  dailyPnl: { date: string; wins: number; losses: number; pnl: number }[];
  latency: { p50: number; p95: number; p99: number };
  slippage: { avg: number; best: number; worst: number };
}

export interface DashboardData {
  user: { name: string; email: string; phone: string; isAdmin: boolean; telegramChatId: string };
  todayPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  pnlPercent: number;
  activeTrades: number;
  brokersOnline: number;
  killSwitchStatus: "ACTIVE" | "TRIPPED";
  killSwitchRemaining: number;
  killSwitchMaxLoss: number;
  killSwitchMaxTrades: number;
  killSwitchAutoSquareOff: boolean;
  winStreak: number;
  totalTradesToday: number;
  winRate: number;
  avgLatencyMs: number;
  equityCurve: { time: string; value: number }[];
  recentTrades: Trade[];
  strategies: Strategy[];
  brokers: Broker[];
  positions: Position[];
  webhooks: WebhookToken[];
  killSwitchHistory: KillSwitchEvent[];
  analytics30d: AnalyticsPeriod;
}

// ─── Mock Data ─────────────────────────────────────────────────────────

const trades: Trade[] = [
  { id: "1", time: "2026-04-17T10:15:00+05:30", action: "BUY", symbol: "NIFTY 25000CE", quantity: 50, price: 125, pnl: 1800, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 35, orderId: "FY-240115-001" },
  { id: "2", time: "2026-04-17T11:30:00+05:30", action: "SELL", symbol: "BANKNIFTY FUT", quantity: 15, price: 52400, pnl: 3200, status: "complete", broker: "Dhan", strategy: "BN Momentum", latencyMs: 28, orderId: "DH-240115-001" },
  { id: "3", time: "2026-04-17T13:45:00+05:30", action: "BUY", symbol: "RELIANCE CE", quantity: 100, price: 340, pnl: -500, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 42, orderId: "FY-240115-002" },
  { id: "4", time: "2026-04-17T14:15:00+05:30", action: "SELL", symbol: "NIFTY 25000PE", quantity: 75, price: 180, pnl: 2100, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 38, orderId: "FY-240115-003" },
  { id: "5", time: "2026-04-17T14:45:00+05:30", action: "BUY", symbol: "INFY FUT", quantity: 25, price: 1850, pnl: 850, status: "complete", broker: "Dhan", strategy: "BN Momentum", latencyMs: 31, orderId: "DH-240115-002" },
  { id: "6", time: "2026-04-16T10:30:00+05:30", action: "BUY", symbol: "TCS CE", quantity: 40, price: 220, pnl: 1200, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 40, orderId: "FY-240114-001" },
  { id: "7", time: "2026-04-16T11:00:00+05:30", action: "SELL", symbol: "NIFTY 24900PE", quantity: 60, price: 95, pnl: -300, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 36, orderId: "FY-240114-002" },
  { id: "8", time: "2026-04-16T14:00:00+05:30", action: "BUY", symbol: "HDFCBANK FUT", quantity: 30, price: 1680, pnl: 1500, status: "complete", broker: "Dhan", strategy: "BN Momentum", latencyMs: 29, orderId: "DH-240114-001" },
  { id: "9", time: "2026-04-15T10:15:00+05:30", action: "SELL", symbol: "BANKNIFTY CE", quantity: 50, price: 420, pnl: 2800, status: "complete", broker: "Dhan", strategy: "BN Momentum", latencyMs: 33, orderId: "DH-240113-001" },
  { id: "10", time: "2026-04-15T13:30:00+05:30", action: "BUY", symbol: "SBIN FUT", quantity: 80, price: 810, pnl: -700, status: "complete", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 45, orderId: "FY-240113-001" },
  { id: "11", time: "2026-04-17T09:20:00+05:30", action: "BUY", symbol: "NIFTY 25100CE", quantity: 100, price: 80, pnl: 0, status: "pending", broker: "Fyers", strategy: "Nifty Scalper", latencyMs: 38, orderId: "FY-240115-004" },
  { id: "12", time: "2026-04-17T09:25:00+05:30", action: "BUY", symbol: "TATAMOTORS CE", quantity: 200, price: 45, pnl: 0, status: "rejected", broker: "Dhan", strategy: "BN Momentum", latencyMs: 0, orderId: "" },
];

export const mockDashboard: DashboardData = {
  user: { name: "Jayesh", email: "jayesh@thetradedeskai.com", phone: "+91-9876543210", isAdmin: true, telegramChatId: "123456789" },
  todayPnl: 12450,
  realizedPnl: 8200,
  unrealizedPnl: 4250,
  pnlPercent: 2.1,
  activeTrades: 5,
  brokersOnline: 2,
  killSwitchStatus: "ACTIVE",
  killSwitchRemaining: 3500,
  killSwitchMaxLoss: 5000,
  killSwitchMaxTrades: 50,
  killSwitchAutoSquareOff: true,
  winStreak: 3,
  totalTradesToday: 12,
  winRate: 80,
  avgLatencyMs: 42,
  equityCurve: [
    { time: "09:15", value: 0 }, { time: "09:30", value: 1200 }, { time: "09:45", value: 800 },
    { time: "10:00", value: 2400 }, { time: "10:15", value: 3800 }, { time: "10:30", value: 3200 },
    { time: "10:45", value: 5100 }, { time: "11:00", value: 6800 }, { time: "11:30", value: 5900 },
    { time: "12:00", value: 7200 }, { time: "12:30", value: 8500 }, { time: "13:00", value: 9100 },
    { time: "13:30", value: 8800 }, { time: "14:00", value: 10200 }, { time: "14:30", value: 11500 },
    { time: "15:00", value: 12000 }, { time: "15:15", value: 12450 },
  ],
  recentTrades: trades.slice(0, 5),
  strategies: [
    { id: "1", name: "Nifty Scalper", winRate: 78, todayPnl: 8200, monthPnl: 45000, totalTrades: 240, todayTrades: 8, isActive: true, broker: "Fyers", webhookConnected: true },
    { id: "2", name: "BN Momentum", winRate: 65, todayPnl: 4250, monthPnl: 28000, totalTrades: 85, todayTrades: 4, isActive: true, broker: "Dhan", webhookConnected: true },
    { id: "3", name: "Options Theta Decay", winRate: 55, todayPnl: 0, monthPnl: -2000, totalTrades: 30, todayTrades: 0, isActive: false, broker: "Fyers", webhookConnected: false },
  ],
  // Only "coming_soon" placeholders. Real connected brokers come
  // exclusively from the API — never fake "connected" entries here,
  // they leak fake activity timestamps onto the Brokers page.
  brokers: [
    { name: "Dhan",     status: "coming_soon", latencyMs: 0, lastLogin: "" },
    { name: "Shoonya",  status: "coming_soon", latencyMs: 0, lastLogin: "" },
    { name: "Zerodha",  status: "coming_soon", latencyMs: 0, lastLogin: "" },
    { name: "Upstox",   status: "coming_soon", latencyMs: 0, lastLogin: "" },
    { name: "AngelOne", status: "coming_soon", latencyMs: 0, lastLogin: "" },
  ],
  positions: [
    { id: "p1", symbol: "NIFTY 25000CE", quantity: 50, avgPrice: 125, ltp: 161, pnl: 1800, broker: "Fyers", side: "LONG" },
    { id: "p2", symbol: "INFY FUT", quantity: 75, avgPrice: 1520, ltp: 1526, pnl: 450, broker: "Dhan", side: "LONG" },
    { id: "p3", symbol: "RELIANCE CE", quantity: 100, avgPrice: 340, ltp: 335, pnl: -500, broker: "Fyers", side: "LONG" },
    { id: "p4", symbol: "BANKNIFTY FUT", quantity: 15, avgPrice: 52400, ltp: 52567, pnl: 2500, broker: "Dhan", side: "LONG" },
  ],
  webhooks: [
    { id: "w1", token: "tb_wh_a1b2c3d4e5f6g7h8", hmacSecret: "hm_s3cr3t_k3y_12345678", label: "Nifty Strategy", strategy: "Nifty Scalper", broker: "Fyers", isActive: true, lastUsed: "2026-04-17T14:45:00+05:30", created: "2026-04-01T09:00:00+05:30" },
    { id: "w2", token: "tb_wh_x9y8z7w6v5u4t3s2", hmacSecret: "hm_s3cr3t_k3y_87654321", label: "BankNifty Strategy", strategy: "BN Momentum", broker: "Dhan", isActive: true, lastUsed: "2026-04-17T11:30:00+05:30", created: "2026-04-05T10:00:00+05:30" },
  ],
  killSwitchHistory: [
    { id: "ks1", triggeredAt: "2026-04-15T14:45:00+05:30", reason: "Daily loss exceeded \u20B95,000", dailyPnl: -5200, positionsClosed: 3, resetAt: "2026-04-15T16:00:00+05:30" },
    { id: "ks2", triggeredAt: "2026-04-10T13:30:00+05:30", reason: "Max daily trades reached (50/50)", dailyPnl: -1800, positionsClosed: 1, resetAt: "2026-04-10T15:30:00+05:30" },
  ],
  analytics30d: {
    winRate: 72, totalPnl: 120000, sharpe: 2.1, totalTrades: 325,
    bestDay: { date: "2026-04-12", pnl: 8200 },
    worstDay: { date: "2026-04-08", pnl: -2100 },
    avgTradesPnl: 369,
    equityCurve: Array.from({ length: 30 }, (_, i) => ({
      date: `Apr ${i + 1}`,
      value: Math.round(4000 * (i + 1) * (0.8 + Math.random() * 0.4)),
    })),
    dailyPnl: Array.from({ length: 30 }, (_, i) => ({
      date: `${i + 1}`,
      wins: Math.floor(Math.random() * 8) + 3,
      losses: Math.floor(Math.random() * 4),
      pnl: Math.round((Math.random() - 0.25) * 8000),
    })),
    latency: { p50: 35, p95: 78, p99: 120 },
    slippage: { avg: 0.02, best: 0.0, worst: 0.15 },
  },
};

export { trades as allTrades };
