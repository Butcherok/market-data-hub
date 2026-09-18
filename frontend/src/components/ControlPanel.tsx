import { useEffect, useState } from "react";
import { api } from "../api";
import type { MarketInfo, ViewTimeframe } from "../types";
import { VIEW_TIMEFRAMES } from "../types";

interface Props {
  onStartCollection: (market: string, symbol: string) => void;
  collecting: boolean;
  onViewChange: (market: string, symbol: string, timeframe: ViewTimeframe) => void;
}

export function ControlPanel({ onStartCollection, collecting, onViewChange }: Props) {
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [market, setMarket] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbolFilter, setSymbolFilter] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState<ViewTimeframe>("1h");
  const [loadingSymbols, setLoadingSymbols] = useState(false);

  useEffect(() => {
    api.getMarkets().then((m) => {
      setMarkets(m);
      if (m.length) setMarket(m[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!market) return;
    setLoadingSymbols(true);
    setSymbol("");
    api.getSymbols(market)
      .then(setSymbols)
      .catch(() => setSymbols([]))
      .finally(() => setLoadingSymbols(false));
  }, [market]);

  useEffect(() => {
    if (market && symbol) onViewChange(market, symbol, timeframe);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [market, symbol, timeframe]);

  const filteredSymbols = symbolFilter
    ? symbols.filter((s) => s.toUpperCase().includes(symbolFilter.toUpperCase()))
    : symbols;

  return (
    <div className="card">
      <h2>Сбор и просмотр данных</h2>
      <div className="row">
        <div className="field">
          <label>Рынок</label>
          <select value={market} onChange={(e) => setMarket(e.target.value)}>
            {markets.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ minWidth: 220 }}>
          <label>Инструмент {loadingSymbols ? "(загрузка…)" : `(${symbols.length})`}</label>
          <input
            list="symbols-list"
            placeholder="напр. USDCUSDT"
            value={symbol}
            onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setSymbolFilter(e.target.value); }}
          />
          <datalist id="symbols-list">
            {filteredSymbols.slice(0, 200).map((s) => <option key={s} value={s} />)}
          </datalist>
        </div>

        <div className="field">
          <label>Таймфрейм просмотра/экспорта</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value as ViewTimeframe)}>
            {VIEW_TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
          </select>
        </div>

        <button
          disabled={!market || !symbol || collecting}
          onClick={() => onStartCollection(market, symbol)}
        >
          {collecting ? "Идёт сбор…" : "Собрать / докачать"}
        </button>

        {market && symbol && (
          <a
            className="secondary"
            style={{ padding: "8px 16px", borderRadius: 7, border: "1px solid var(--border)", textDecoration: "none", color: "var(--text-primary)" }}
            href={api.exportUrl(market, symbol, timeframe)}
          >
            Экспорт CSV ({timeframe})
          </a>
        )}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-secondary)" }}>
        С биржи всегда собираются минутные бары (1m) — единственный источник правды.
        Таймфрейм выше влияет только на график/экспорт (ресемплинг из 1m на лету).
      </div>
    </div>
  );
}
