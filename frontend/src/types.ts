export interface MarketInfo {
  id: string;
  label: string;
}

export interface SummaryRow {
  market: string;
  symbol: string;
  bar_count: number;
  first_open_time: number;
  last_open_time: number;
  gap_count: number;
  missing_bars: number;
}

export interface Summary {
  markets: SummaryRow[];
  db_file_size_bytes: number;
}

export type JobStatus = "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  market: string;
  symbol: string;
  status: JobStatus;
  bars_fetched: number;
  gaps_detected: number;
  last_open_time: number | null;
  started_at: number;
  finished_at: number | null;
  error: string | null;
}

export interface JobHistoryRow {
  job_id: string;
  market: string;
  symbol: string;
  interval: string;
  started_at: number;
  finished_at: number | null;
  bars_fetched: number;
  gaps_detected: number;
  status: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export const VIEW_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"] as const;
export type ViewTimeframe = (typeof VIEW_TIMEFRAMES)[number];
