import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi } from "lightweight-charts";
import type { Candle } from "../types";

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function Chart({ candles, symbol, timeframe }: { candles: Candle[]; symbol: string; timeframe: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: cssVar("--surface-1") },
        textColor: cssVar("--text-secondary"),
      },
      grid: {
        vertLines: { color: cssVar("--gridline") },
        horzLines: { color: cssVar("--gridline") },
      },
      rightPriceScale: { borderColor: cssVar("--border") },
      timeScale: { borderColor: cssVar("--border"), timeVisible: true },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;

    const series = chart.addCandlestickSeries({
      upColor: cssVar("--series-green"),
      downColor: cssVar("--series-red"),
      borderUpColor: cssVar("--series-green"),
      borderDownColor: cssVar("--series-red"),
      wickUpColor: cssVar("--series-green"),
      wickDownColor: cssVar("--series-red"),
    });
    series.setData(candles.map((c) => ({
      time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close,
    })));
    chart.timeScale().fitContent();

    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [candles]);

  return (
    <div className="card">
      <h2>{symbol ? `${symbol} · ${timeframe}` : "Предпросмотр"}</h2>
      {candles.length === 0 ? (
        <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>
          Нет данных для выбранного инструмента — запусти сбор выше.
        </div>
      ) : (
        <div ref={containerRef} />
      )}
    </div>
  );
}
