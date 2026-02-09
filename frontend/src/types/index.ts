/** Shared TypeScript types mirroring backend domain models. */

// -- Trade types --

export type TradeType = "mua_chu_dong" | "ban_chu_dong" | "neutral";

export interface SessionStats {
  symbol: string;
  mua_chu_dong_volume: number;
  mua_chu_dong_value: number;
  ban_chu_dong_volume: number;
  ban_chu_dong_value: number;
  neutral_volume: number;
  total_volume: number;
  last_updated: string | null;
}

// -- Price data --

export interface PriceData {
  last_price: number;
  change: number;
  change_pct: number;
  ref_price: number;
  ceiling: number;
  floor: number;
}

// -- Foreign investor --

export interface ForeignInvestorData {
  symbol: string;
  buy_volume: number;
  sell_volume: number;
  net_volume: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  total_room: number;
  current_room: number;
  buy_speed_per_min: number;
  sell_speed_per_min: number;
  buy_acceleration: number;
  sell_acceleration: number;
  last_updated: string | null;
}

export interface ForeignSummary {
  total_buy_value: number;
  total_sell_value: number;
  total_net_value: number;
  total_buy_volume: number;
  total_sell_volume: number;
  total_net_volume: number;
  top_buy: ForeignInvestorData[];
  top_sell: ForeignInvestorData[];
}

// -- Index --

export interface IntradayPoint {
  timestamp: string;
  value: number;
}

export interface IndexData {
  index_id: string;
  value: number;
  prior_value: number;
  change: number;
  ratio_change: number;
  total_volume: number;
  advances: number;
  declines: number;
  no_changes: number;
  intraday: IntradayPoint[];
  advance_ratio: number;
  last_updated: string | null;
}

// -- Derivatives --

export interface BasisPoint {
  timestamp: string;
  futures_symbol: string;
  futures_price: number;
  spot_value: number;
  basis: number;
  basis_pct: number;
  is_premium: boolean;
}

export interface DerivativesData {
  symbol: string;
  last_price: number;
  change: number;
  change_pct: number;
  volume: number;
  bid_price: number;
  ask_price: number;
  basis: number;
  basis_pct: number;
  is_premium: boolean;
  last_updated: string | null;
}

export interface DerivativesHistory {
  contract: string;
  timestamp: string;
  price: number;
  basis: number;
  open_interest: number;
}

// -- Unified snapshot --

export interface MarketSnapshot {
  quotes: Record<string, SessionStats>;
  prices: Record<string, PriceData>;
  indices: Record<string, IndexData>;
  foreign: ForeignSummary | null;
  derivatives: DerivativesData | null;
}

// -- API response wrappers --

export interface ForeignDetailResponse {
  summary: ForeignSummary;
  stocks: ForeignInvestorData[];
}

export interface VolumeStatsResponse {
  stats: SessionStats[];
}

// -- Signals (mock until analytics engine) --

export type SignalType = "foreign" | "volume" | "divergence";
export type SignalSeverity = "info" | "warning" | "critical";

export interface Signal {
  id: string;
  type: SignalType;
  severity: SignalSeverity;
  symbol: string;
  message: string;
  value: number;
  timestamp: string;
}
