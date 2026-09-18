import { useCallback, useEffect, useState } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { ProgressPanel } from "./components/ProgressPanel";
import { SummaryCards } from "./components/SummaryCards";
import { Chart } from "./components/Chart";
import { JobsHistory } from "./components/JobsHistory";
import { api } from "./api";
import type { Candle, JobHistoryRow, Summary, ViewTimeframe } from "./types";

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<JobHistoryRow[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobRunning, setJobRunning] = useState(false);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [viewMarket, setViewMarket] = useState("");
  const [viewSymbol, setViewSymbol] = useState("");
  const [viewTimeframe, setViewTimeframe] = useState<ViewTimeframe>("1h");
  const [authToken, setAuthToken] = useState(localStorage.getItem("mdh_auth_token") || "");
  const [whoami, setWhoami] = useState<{ name: string | null; auth_required: boolean } | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);

  // Именной токен-ссылка: ?token=... в адресе подхватывается один раз при
  // заходе, сохраняется в localStorage и убирается из адресной строки (чтобы
  // не осталась в истории браузера/при пересылке скриншота адреса).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      localStorage.setItem("mdh_auth_token", urlToken);
      setAuthToken(urlToken);
      params.delete("token");
      const rest = params.toString();
      const newUrl = window.location.pathname + (rest ? `?${rest}` : "") + window.location.hash;
      window.history.replaceState({}, "", newUrl);
    }
  }, []);

  const refreshWhoami = useCallback(() => {
    api.whoami().then(setWhoami).catch(() => setWhoami(null));
  }, []);

  const refreshSummary = useCallback(() => {
    api.getSummary().then(setSummary).catch(() => {});
    api.listJobs().then((r) => setHistory(r.history)).catch(() => {});
  }, []);

  useEffect(() => { refreshSummary(); refreshWhoami(); }, [refreshSummary, refreshWhoami]);

  const handleStartCollection = async (market: string, symbol: string) => {
    setJobError(null);
    setJobRunning(true);
    try {
      const job = await api.startJob(market, symbol);
      setActiveJobId(job.id);
    } catch (e: any) {
      setJobRunning(false);
      setJobError(String(e?.message || e));
    }
  };

  const handleViewChange = useCallback((market: string, symbol: string, timeframe: ViewTimeframe) => {
    setViewMarket(market);
    setViewSymbol(symbol);
    setViewTimeframe(timeframe);
    api.getPreview(market, symbol, timeframe).then(setCandles).catch(() => setCandles([]));
  }, []);

  const handleFinished = useCallback(() => {
    // activeJobId остаётся — панель прогресса продолжает показывать финальный
    // статус (completed/failed/cancelled), пока не начнётся новый сбор.
    refreshSummary();
    if (viewMarket && viewSymbol) {
      api.getPreview(viewMarket, viewSymbol, viewTimeframe).then(setCandles).catch(() => {});
    }
  }, [refreshSummary, viewMarket, viewSymbol, viewTimeframe]);

  const saveToken = () => {
    if (authToken) localStorage.setItem("mdh_auth_token", authToken);
    else localStorage.removeItem("mdh_auth_token");
    refreshSummary();
    refreshWhoami();
  };

  return (
    <div className="app">
      <div className="app-header">
        <div>
          <h1>Market Data Hub</h1>
          <div className="subtitle">Сбор и просмотр рыночных данных Binance (spot / USDⓈ-M futures)</div>
        </div>
        <div className="row" style={{ alignItems: "center", gap: 8 }}>
          {whoami?.name && (
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Вы: <b>{whoami.name}</b></div>
          )}
          {whoami?.auth_required && !whoami?.name && (
            <div style={{ fontSize: 12, color: "var(--danger, #d33)" }}>токен не распознан</div>
          )}
          <input
            type="password"
            placeholder="токен доступа (если настроен)"
            value={authToken}
            onChange={(e) => setAuthToken(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 7, border: "1px solid var(--border)", background: "var(--page)", color: "var(--text-primary)", fontSize: 12 }}
          />
          <button className="secondary" onClick={saveToken} style={{ padding: "6px 12px", fontSize: 12 }}>OK</button>
        </div>
      </div>

      {jobError && (
        <div className="card" style={{ borderColor: "var(--danger, #d33)", color: "var(--danger, #d33)", fontSize: 13 }}>
          Не удалось запустить сбор: {jobError}
        </div>
      )}

      <SummaryCards summary={summary} />

      <ControlPanel
        onStartCollection={handleStartCollection}
        collecting={jobRunning}
        onViewChange={handleViewChange}
      />

      <ProgressPanel jobId={activeJobId} onFinished={handleFinished} onStatusChange={(s) => setJobRunning(s === "running")} />

      <Chart candles={candles} symbol={viewSymbol} timeframe={viewTimeframe} />

      <div className="card">
        <h2>Экспорт всей базы</h2>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 10 }}>
          Полный файл SQLite (все рынки, все символы, сырые минутки) — для бэктеста напрямую, без похода через UI.
        </div>
        <a href={api.downloadDbUrl()} style={{ textDecoration: "none" }}>
          <button className="secondary">Скачать market_data.db</button>
        </a>
      </div>

      <JobsHistory history={history} />
    </div>
  );
}
