"""
[DATA-COLLECTION UTILITY] — не торговая логика, чек-лист боевого бота
(раздел 5 project instructions) к этому файлу не применяется.

Основная логика сбора — адаптация fetch_market_data.py под вызов из веб-job'ы:
те же функции, но с колбэком прогресса и флагом отмены между батчами вместо
блокирующего цикла с print(). CLI-версия (fetch_market_data.py) остаётся
рабочей самостоятельно — этот модуль её не заменяет, а переиспользует для UI.
"""
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from config import MARKETS, INTERVAL, INTERVAL_MS

SCRIPT_VERSION = "web-1.0.0-2026-09-18"


class RateLimitedSession:
    def __init__(self, max_retries: int = 8):
        self.session = requests.Session()
        self.max_retries = max_retries

    def get(self, url: str, params: dict, log: Callable[[str], None]) -> list:
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.get(url, params=params, timeout=20)
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise
                sleep_s = min(2 ** attempt, 60)
                log(f"сетевая ошибка ({exc}), retry {attempt}/{self.max_retries} через {sleep_s}с")
                time.sleep(sleep_s)
                continue

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (429, 418):
                retry_after = int(resp.headers.get("Retry-After", 0))
                sleep_s = max(retry_after, min(2 ** attempt, 120))
                log(f"rate limit {resp.status_code}, ждём {sleep_s}с (попытка {attempt})")
                time.sleep(sleep_s)
                if attempt > self.max_retries:
                    resp.raise_for_status()
                continue

            if attempt > self.max_retries:
                resp.raise_for_status()
            sleep_s = min(2 ** attempt, 60)
            log(f"HTTP {resp.status_code}, retry {attempt}/{self.max_retries} через {sleep_s}с")
            time.sleep(sleep_s)


def get_earliest_open_time(http: RateLimitedSession, market: str, symbol: str, log) -> int:
    cfg = MARKETS[market]
    url = cfg["base_url"] + cfg["klines_path"]
    data = http.get(url, {"symbol": symbol, "interval": INTERVAL, "startTime": 0, "limit": 1}, log)
    if not data:
        raise RuntimeError(f"{market}/{symbol}: биржа не вернула ни одного бара")
    return int(data[0][0])


def fetch_symbol_filters(http: RateLimitedSession, market: str, symbol: str, log) -> dict:
    cfg = MARKETS[market]
    url = cfg["base_url"] + cfg["exchange_info_path"]
    params = {"symbol": symbol} if market == "spot" else {}
    info = http.get(url, params, log)
    symbols = info.get("symbols", []) if isinstance(info, dict) else []
    result = {"tick_size": None, "step_size": None, "min_notional": None, "onboard_time": None}
    for s in symbols:
        if s.get("symbol") != symbol:
            continue
        result["onboard_time"] = s.get("onboardDate")
        for f in s.get("filters", []):
            ftype = f.get("filterType")
            if ftype == "PRICE_FILTER":
                result["tick_size"] = float(f["tickSize"])
            elif ftype == "LOT_SIZE":
                result["step_size"] = float(f["stepSize"])
            elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                result["min_notional"] = float(f.get("notional") or f.get("minNotional") or 0)
        break
    return result


def list_symbols(http: RateLimitedSession, market: str, log) -> list[str]:
    """Живой список торгуемых символов с биржи (не хардкод)."""
    cfg = MARKETS[market]
    url = cfg["base_url"] + cfg["exchange_info_path"]
    info = http.get(url, {}, log)
    symbols = info.get("symbols", []) if isinstance(info, dict) else []
    active_status = {"TRADING"}
    out = []
    for s in symbols:
        status = s.get("status") or s.get("contractStatus")
        if status in active_status:
            out.append(s["symbol"])
    return sorted(out)


def now_ms() -> int:
    return int(time.time() * 1000)


def upsert_klines(conn, market: str, symbol: str, rows: list) -> int:
    ts = now_ms()
    payload = [
        (market, symbol, int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]),
         float(r[5]), int(r[6]), float(r[7]), int(r[8]), float(r[9]), float(r[10]), ts)
        for r in rows
    ]
    cur = conn.executemany(
        """INSERT OR IGNORE INTO klines
           (market, symbol, open_time, open, high, low, close, volume,
            close_time, quote_volume, num_trades, taker_buy_base_volume,
            taker_buy_quote_volume, ingested_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        payload,
    )
    return cur.rowcount


def detect_and_log_gaps(conn, market: str, symbol: str, rows: list) -> int:
    gaps_found = 0
    ts = now_ms()
    for prev, cur in zip(rows, rows[1:]):
        delta = int(cur[0]) - int(prev[0])
        if delta > INTERVAL_MS:
            missing = delta // INTERVAL_MS - 1
            conn.execute(
                """INSERT INTO gaps (market, symbol, gap_start_open_time, gap_end_open_time,
                                      missing_bars, detected_at) VALUES (?,?,?,?,?,?)""",
                (market, symbol, int(prev[0]), int(cur[0]), missing, ts),
            )
            gaps_found += 1
    return gaps_found


def run_collection(
    conn,
    market: str,
    symbol: str,
    job_id: str,
    log: Callable[[str], None],
    progress: Callable[[dict], None],
    should_cancel: Callable[[], bool],
    end_time_ms: Optional[int] = None,
):
    """Выполняет докачку 1m-баров до end_time_ms (по умолчанию — сейчас).
    Вызывает log(строка) для каждой строки прогресса и progress(dict) для
    обновления счётчиков job'ы. should_cancel() проверяется между батчами."""
    cfg = MARKETS[market]
    http = RateLimitedSession()

    run_id = conn.execute(
        """INSERT INTO collection_log (job_id, market, symbol, interval, script_version, started_at, status)
           VALUES (?,?,?,?,?,?, 'running')""",
        (job_id, market, symbol, INTERVAL, SCRIPT_VERSION, now_ms()),
    ).lastrowid
    conn.commit()

    log(f"=== {market}/{symbol}: старт ===")
    filters = fetch_symbol_filters(http, market, symbol, log)
    earliest = get_earliest_open_time(http, market, symbol, log)
    conn.execute(
        """INSERT INTO symbols_meta (market, symbol, tick_size, step_size, min_notional,
               onboard_time, earliest_kline_open_time, updated_at)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(market, symbol) DO UPDATE SET
             tick_size=excluded.tick_size, step_size=excluded.step_size,
             min_notional=excluded.min_notional, onboard_time=excluded.onboard_time,
             earliest_kline_open_time=excluded.earliest_kline_open_time,
             updated_at=excluded.updated_at""",
        (market, symbol, filters["tick_size"], filters["step_size"],
         filters["min_notional"], filters["onboard_time"], earliest, now_ms()),
    )
    conn.commit()
    log(f"earliest_open_time={datetime.fromtimestamp(earliest/1000, tz=timezone.utc)} "
        f"tick={filters['tick_size']} step={filters['step_size']} min_notional={filters['min_notional']}")

    row = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE market=? AND symbol=?", (market, symbol),
    ).fetchone()
    resume_from = (row[0] + INTERVAL_MS) if row and row[0] is not None else earliest
    if resume_from > earliest:
        log(f"резюме с {datetime.fromtimestamp(resume_from/1000, tz=timezone.utc)} (уже есть в БД)")

    url = cfg["base_url"] + cfg["klines_path"]
    limit = cfg["max_limit"]
    total_bars = 0
    total_gaps = 0
    start_time = resume_from
    end_time = end_time_ms or now_ms()
    prev_last_row = None
    status = "completed"

    try:
        while start_time < end_time:
            if should_cancel():
                status = "cancelled"
                log("отменено пользователем")
                break

            batch = http.get(url, {"symbol": symbol, "interval": INTERVAL,
                                     "startTime": start_time, "limit": limit}, log)
            if not batch:
                break

            check_rows = ([prev_last_row] + batch) if prev_last_row else batch
            total_gaps += detect_and_log_gaps(conn, market, symbol, check_rows)

            inserted = upsert_klines(conn, market, symbol, batch)
            total_bars += inserted
            conn.commit()

            prev_last_row = batch[-1]
            last_open_time = int(batch[-1][0])
            start_time = last_open_time + INTERVAL_MS

            progress({
                "bars_fetched": total_bars, "gaps_detected": total_gaps,
                "last_open_time": last_open_time,
            })
            log(f"+{inserted} баров, до {datetime.fromtimestamp(last_open_time/1000, tz=timezone.utc)}")

            if len(batch) < limit:
                break
            time.sleep(0.25)

        conn.execute(
            "UPDATE collection_log SET finished_at=?, bars_fetched=?, gaps_detected=?, status=? WHERE run_id=?",
            (now_ms(), total_bars, total_gaps, status, run_id),
        )
        conn.commit()
        log(f"=== {market}/{symbol}: {status}, +{total_bars} баров, {total_gaps} дыр ===")
        return status, total_bars, total_gaps

    except Exception as exc:
        conn.execute(
            "UPDATE collection_log SET finished_at=?, bars_fetched=?, gaps_detected=?, status='failed' WHERE run_id=?",
            (now_ms(), total_bars, total_gaps, run_id),
        )
        conn.commit()
        log(f"ОШИБКА: {exc}")
        raise
