"""
Простой in-process менеджер фоновых job'ов сбора данных. Однопользовательский
инструмент — Celery/Redis избыточны, обычный поток + блокировка достаточны.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field

import db as dbmod
import collector


@dataclass
class Job:
    id: str
    market: str
    symbol: str
    status: str = "running"  # running | completed | failed | cancelled
    bars_fetched: int = 0
    gaps_detected: int = 0
    last_open_time: int | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    log: list[str] = field(default_factory=list)
    error: str | None = None
    _cancel: threading.Event = field(default_factory=threading.Event)

    def to_dict(self):
        return {
            "id": self.id, "market": self.market, "symbol": self.symbol,
            "status": self.status, "bars_fetched": self.bars_fetched,
            "gaps_detected": self.gaps_detected, "last_open_time": self.last_open_time,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "error": self.error,
        }


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def active_job_for(self, market: str, symbol: str) -> Job | None:
        with self._lock:
            for j in self._jobs.values():
                if j.market == market and j.symbol == symbol and j.status == "running":
                    return j
        return None

    def start(self, market: str, symbol: str) -> Job:
        existing = self.active_job_for(market, symbol)
        if existing:
            return existing

        job = Job(id=uuid.uuid4().hex[:12], market=market, symbol=symbol)
        with self._lock:
            self._jobs[job.id] = job

        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()
        return job

    def _run(self, job: Job):
        conn = dbmod.get_conn()

        def log(line: str):
            job.log.append(line)
            if len(job.log) > 2000:
                del job.log[:1000]

        def progress(fields: dict):
            job.bars_fetched = fields.get("bars_fetched", job.bars_fetched)
            job.gaps_detected = fields.get("gaps_detected", job.gaps_detected)
            job.last_open_time = fields.get("last_open_time", job.last_open_time)

        try:
            status, bars, gaps = collector.run_collection(
                conn, job.market, job.symbol, job.id, log, progress,
                should_cancel=lambda: job._cancel.is_set(),
            )
            job.status = status
            job.bars_fetched = bars
            job.gaps_detected = gaps
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = time.time()

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status != "running":
            return False
        job._cancel.set()
        return True

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)


manager = JobManager()
