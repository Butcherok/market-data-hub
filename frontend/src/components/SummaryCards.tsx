import type { Summary } from "../types";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} Б`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} КБ`;
  return `${(n / 1024 ** 2).toFixed(1)} МБ`;
}

function fmtDate(ms: number | null): string {
  if (!ms) return "—";
  return new Date(ms).toISOString().slice(0, 10);
}

export function SummaryCards({ summary }: { summary: Summary | null }) {
  if (!summary) return null;
  const totalBars = summary.markets.reduce((s, m) => s + m.bar_count, 0);
  const totalGaps = summary.markets.reduce((s, m) => s + m.gap_count, 0);

  return (
    <div className="card">
      <h2>Состояние базы данных</h2>
      <div className="stat-grid">
        <div className="stat-tile">
          <div className="label">Всего баров (1m)</div>
          <div className="value">{totalBars.toLocaleString("ru-RU")}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Размер файла БД</div>
          <div className="value">{fmtBytes(summary.db_file_size_bytes)}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Пар в базе</div>
          <div className="value">{summary.markets.length}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Обнаружено дыр</div>
          <div className="value">{totalGaps}</div>
        </div>
      </div>

      {summary.markets.length > 0 && (
        <div className="table-scroll">
        <table style={{ marginTop: 14 }}>
          <thead>
            <tr>
              <th>Рынок</th>
              <th>Символ</th>
              <th className="num">Баров</th>
              <th>С</th>
              <th>По</th>
              <th className="num">Дыр</th>
            </tr>
          </thead>
          <tbody>
            {summary.markets.map((m) => (
              <tr key={`${m.market}-${m.symbol}`}>
                <td>{m.market}</td>
                <td>{m.symbol}</td>
                <td className="num">{m.bar_count.toLocaleString("ru-RU")}</td>
                <td>{fmtDate(m.first_open_time)}</td>
                <td>{fmtDate(m.last_open_time)}</td>
                <td className="num">{m.gap_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}
