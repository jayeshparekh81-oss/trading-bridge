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
}

export interface Strategy {
  id: string;
  name: string;
  winRate: number;
  todayPnl: number;
  totalTrades: number;
  isActive: boolean;
}

export interface DashboardData {
  user: { name: string; email: string; isAdmin: boolean };
  todayPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  pnlPercent: number;
  activeTrades: number;
  brokersOnline: number;
  killSwitchStatus: "ACTIVE" | "TRIPPED";
  killSwitchRemaining: number;
  winStreak: number;
  totalTradesToday: number;
  winRate: number;
  avgLatencyMs: number;
  equityCurve: { time: string; value: number }[];
  recentTrades: Trade[];
  strategies: Strategy[];
}

export const mockDashboard: DashboardData = {
  user: { name: "Jayesh", email: "jayesh@tradingbridge.in", isAdmin: true },
  todayPnl: 12450,
  realizedPnl: 8200,
  unrealizedPnl: 4250,
  pnlPercent: 2.1,
  activeTrades: 5,
  brokersOnline: 2,
  killSwitchStatus: "ACTIVE",
  killSwitchRemaining: 3500,
  winStreak: 3,
  totalTradesToday: 12,
  winRate: 80,
  avgLatencyMs: 42,
  equityCurve: [
    { time: "09:15", value: 0 },
    { time: "09:30", value: 1200 },
    { time: "09:45", value: 800 },
    { time: "10:00", value: 2400 },
    { time: "10:15", value: 3800 },
    { time: "10:30", value: 3200 },
    { time: "10:45", value: 5100 },
    { time: "11:00", value: 6800 },
    { time: "11:30", value: 5900 },
    { time: "12:00", value: 7200 },
    { time: "12:30", value: 8500 },
    { time: "13:00", value: 9100 },
    { time: "13:30", value: 8800 },
    { time: "14:00", value: 10200 },
    { time: "14:30", value: 11500 },
    { time: "15:00", value: 12000 },
    { time: "15:15", value: 12450 },
  ],
  recentTrades: [
    { id: "1", time: "2024-01-15T10:15:00Z", action: "BUY", symbol: "NIFTY 25000CE", quantity: 50, price: 125, pnl: 1800, status: "complete", broker: "Fyers", strategy: "Nifty Scalper" },
    { id: "2", time: "2024-01-15T11:30:00Z", action: "SELL", symbol: "BANKNIFTY FUT", quantity: 15, price: 52400, pnl: 3200, status: "complete", broker: "Dhan", strategy: "BN Momentum" },
    { id: "3", time: "2024-01-15T13:45:00Z", action: "BUY", symbol: "RELIANCE CE", quantity: 100, price: 340, pnl: -500, status: "complete", broker: "Fyers", strategy: "Nifty Scalper" },
    { id: "4", time: "2024-01-15T14:15:00Z", action: "SELL", symbol: "NIFTY 25000PE", quantity: 75, price: 180, pnl: 2100, status: "complete", broker: "Fyers", strategy: "Nifty Scalper" },
    { id: "5", time: "2024-01-15T14:45:00Z", action: "BUY", symbol: "INFY FUT", quantity: 25, price: 1850, pnl: 850, status: "complete", broker: "Dhan", strategy: "BN Momentum" },
  ],
  strategies: [
    { id: "1", name: "Nifty Scalper", winRate: 78, todayPnl: 8200, totalTrades: 8, isActive: true },
    { id: "2", name: "BN Momentum", winRate: 65, todayPnl: 4250, totalTrades: 4, isActive: true },
  ],
};
