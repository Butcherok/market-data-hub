"""
Слой БД: схема, подключение, выборки. Сырые данные (klines) отдельно от
лога дыр (gaps) — без синтетических/дозаполненных строк в klines (см. бриф
проекта: политика пропусков решается на этапе анализа, не сбора).
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    market                  TEXT    NOT NULL,
    symbol                  TEXT    NOT NULL,
    open_time               INTEGER NOT NULL,
    open                    REAL    NOT NULL,
    high                    REAL    NOT NULL,
    low                     REAL    NOT NULL,
    close                   REAL    NOT NULL,
    volume                  REAL    NOT NULL,
    close_time              INTEGER NOT NULL,
    quote_volume            REAL    NOT NULL,
    num_trades              INTEGER NOT NULL,
    taker_buy_base_volume   REAL    NOT NULL,
    taker_buy_quote_volume  REAL    NOT NULL,
    ingested_at             INTEGER NOT NULL,
    PRIMARY KEY (market, symbol, open_time)
);

CREATE TABLE IF NOT EXISTS gaps (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    market                  TEXT    NOT NULL,
    symbol                  TEXT    NOT NULL,
    gap_start_open_time     INTEGER NOT NULL,
    gap_end_open_time       INTEGER NOT NULL,
    missing_bars            INTEGER NOT NULL,
    detected_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols_meta (
    market                  TEXT    NOT NULL,
    symbol                  TEXT    NOT NULL,
    tick_size               REAL,
    step_size               REAL,
    min_notional            REAL,
    onboard_time            INTEGER,
    earliest_kline_open_time INTEGER,
    updated_at              INTEGER NOT NULL,
    PRIMARY KEY (market, symbol)
);

CREATE TABLE IF NOT EXISTS collection_log (
    run_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT,
    market                  TEXT    NOT NULL,
    symbol                  TEXT    NOT NULL,
    interval                TEXT    NOT NULL,
    script_version          TEXT    NOT NULL,
    started_at              INTEGER NOT NULL,
    finished_at             INTEGER,
    bars_fetched            INTEGER DEFAULT 0,
    gaps_detected           INTEGER DEFAULT 0,
    status                  TEXT    NOT NULL
);
"""

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _ensure_schema(conn: sqlite3.Connection):
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if not _initialized:
            conn.executescript(SCHEMA)
            conn.commit()
            _initialized = True


def get_conn() -> sqlite3.Connection:
    """Одно соединение на поток (SQLite-объекты не шарятся между потоками)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        _ensure_dir()
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        _local.conn = conn
    return conn


@contextmanager
def db():
    yield get_conn()


def get_summary(conn: sqlite3.Connection) -> list[dict]:
    out = []
    rows = conn.execute("SELECT DISTINCT market, symbol FROM klines ORDER BY market, symbol").fetchall()
    for r in rows:
        market, symbol = r["market"], r["symbol"]
        cnt, mn, mx = conn.execute(
            "SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM klines WHERE market=? AND symbol=?",
            (market, symbol),
        ).fetchone()
        gcount, gmissing = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(missing_bars),0) FROM gaps WHERE market=? AND symbol=?",
            (market, symbol),
        ).fetchone()
        out.append({
            "market": market, "symbol": symbol, "bar_count": cnt,
            "first_open_time": mn, "last_open_time": mx,
            "gap_count": gcount, "missing_bars": gmissing,
        })
    return out


def get_gaps(conn: sqlite3.Connection, market: str, symbol: str) -> list[dict]:
    rows = conn.execute(
        """SELECT gap_start_open_time, gap_end_open_time, missing_bars, detected_at
           FROM gaps WHERE market=? AND symbol=? ORDER BY gap_start_open_time""",
        (market, symbol),
    ).fetchall()
    return [dict(r) for r in rows]


def list_jobs_log(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT job_id, market, symbol, interval, started_at, finished_at,
                  bars_fetched, gaps_detected, status
           FROM collection_log ORDER BY run_id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_db_file_size() -> int:
    try:
        return os.path.getsize(DB_PATH)
    except OSError:
        return 0
