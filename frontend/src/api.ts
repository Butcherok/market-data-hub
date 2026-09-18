import type { Candle, Job, JobHistoryRow, MarketInfo, Summary } from "./types";

// Базовый URL бэкенда. По умолчанию — тот же хост, что отдал страницу, порт 8000
// (так работает и на localhost, и через Tailscale/туннель без дополнительной
// настройки). Можно переопределить через VITE_API_BASE при сборке.
const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`;

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("mdh_auth_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  whoami: () => req<{ name: string | null; auth_required: boolean }>("/api/whoami"),
  getMarkets: () => req<MarketInfo[]>("/api/markets"),
  getSymbols: (market: string) => req<string[]>(`/api/symbols?market=${encodeURIComponent(market)}`),
  getSummary: () => req<Summary>("/api/summary"),
  getGaps: (market: string, symbol: string) =>
    req<any[]>(`/api/gaps?market=${market}&symbol=${symbol}`),
  startJob: (market: string, symbol: string) =>
    req<Job>(`/api/jobs?market=${market}&symbol=${symbol}`, { method: "POST" }),
  listJobs: () => req<{ active: Job[]; history: JobHistoryRow[] }>("/api/jobs"),
  getJob: (id: string) => req<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) => req<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  getPreview: (market: string, symbol: string, timeframe: string, start?: number, end?: number) => {
    const params = new URLSearchParams({ market, symbol, timeframe });
    if (start) params.set("start", String(start));
    if (end) params.set("end", String(end));
    return req<Candle[]>(`/api/data/preview?${params.toString()}`);
  },
  exportUrl: (market: string, symbol: string, timeframe: string, start?: number, end?: number) => {
    const params = new URLSearchParams({ market, symbol, timeframe });
    if (start) params.set("start", String(start));
    if (end) params.set("end", String(end));
    return `${API_BASE}/api/data/export?${params.toString()}`;
  },
  downloadDbUrl: () => `${API_BASE}/api/data/download-db`,
  streamUrl: (jobId: string) => `${API_BASE}/api/jobs/${jobId}/stream`,
};

export { API_BASE };
