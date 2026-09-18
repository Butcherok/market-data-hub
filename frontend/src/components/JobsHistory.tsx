import type { JobHistoryRow } from "../types";

function fmtDateTime(ms: number | null): string {
  if (!ms) return "—";
  return new Date(ms).toLocaleString("ru-RU");
}

export function JobsHistory({ history }: { history: JobHistoryRow[] }) {
  if (history.length === 0) return null;
  return (
    <div className="card">
      <h2>История запусков</h2>
      <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Рынок</th>
            <th>Символ</th>
            <th>Начало</th>
            <th>Конец</th>
            <th className="num">Баров</th>
            <th className="num">Дыр</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {history.map((h, i) => (
            <tr key={i}>
              <td>{h.market}</td>
              <td>{h.symbol}</td>
              <td>{fmtDateTime(h.started_at)}</td>
              <td>{fmtDateTime(h.finished_at)}</td>
              <td className="num">{h.bars_fetched.toLocaleString("ru-RU")}</td>
              <td className="num">{h.gaps_detected}</td>
              <td><span className={`badge ${h.status}`}>{h.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
