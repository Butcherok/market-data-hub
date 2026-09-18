import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Job } from "../types";

interface Props {
  jobId: string | null;
  onFinished: () => void;
  onStatusChange?: (status: Job["status"]) => void;
}

export function ProgressPanel({ jobId, onFinished, onStatusChange }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!jobId) return;
    setLines([]);
    setJob(null);
    onStatusChange?.("running");

    const es = new EventSource(api.streamUrl(jobId));
    es.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") {
        setLines((prev) => [...prev, msg.line]);
      } else if (msg.type === "status") {
        setJob(msg);
        if (msg.status !== "running") {
          es.close();
          onStatusChange?.(msg.status);
          onFinished();
        }
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [lines]);

  if (!jobId) return null;

  return (
    <div className="card">
      <h2>Ход сбора {job && <span className={`badge ${job.status}`} style={{ marginLeft: 8 }}>{job.status}</span>}</h2>
      {job && (
        <div className="stat-grid" style={{ marginBottom: 10 }}>
          <div className="stat-tile">
            <div className="label">Инструмент</div>
            <div className="value" style={{ fontSize: 15 }}>{job.market}/{job.symbol}</div>
          </div>
          <div className="stat-tile">
            <div className="label">Баров собрано</div>
            <div className="value">{job.bars_fetched.toLocaleString("ru-RU")}</div>
          </div>
          <div className="stat-tile">
            <div className="label">Дыр найдено</div>
            <div className="value">{job.gaps_detected}</div>
          </div>
        </div>
      )}
      <div className="log-box" ref={logRef}>
        {lines.join("\n")}
      </div>
      {job?.status === "running" && (
        <button className="secondary" style={{ marginTop: 10 }} onClick={() => api.cancelJob(jobId)}>
          Отменить
        </button>
      )}
      {job?.error && <div style={{ color: "var(--status-critical)", marginTop: 8 }}>Ошибка: {job.error}</div>}
    </div>
  );
}
