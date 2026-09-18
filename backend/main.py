"""
[DATA-COLLECTION UTILITY] — веб-обвязка над сбором рыночных данных Binance.
Не торговая логика, чек-лист боевого бота к этому файлу не применяется.

Запуск: uvicorn main:app --host 0.0.0.0 --port 8000
(см. README.md для установки зависимостей, доступа через Tailscale и
публикации наружу через Cloudflare Tunnel)

Авторизация — персональные токены на человека (см. auth.py, manage_users.py),
не общий секрет. Пока в БД нет ни одного пользователя, все /api/* открыты
(рассчитано на то, что доступ и так ограничен сетью — localhost/Tailscale).
Как только через manage_users.py создан первый пользователь — КАЖДЫЙ
запрос от КАЖДОГО, включая владельца, требует валидный Bearer-токен.
"""
import csv
import io
import json
import time
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

import auth
import db as dbmod
import jobs as jobsmod
from collector import RateLimitedSession, list_symbols
from config import MARKETS, VIEW_TIMEFRAMES, ALLOWED_ORIGIN, DB_PATH

app = FastAPI(title="Market Data Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_symbols_cache: dict[str, tuple[float, list[str]]] = {}
SYMBOLS_CACHE_TTL = 300


def check_auth(request: Request, authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Возвращает словарь пользователя {id, name} если авторизация настроена и
    токен валиден; None, если авторизация ещё не настроена (пользователей нет
    в БД — старый режим, доступ ограничен только сетью). Логирует обращение,
    если пользователь определён."""
    conn = dbmod.get_conn()
    if not auth.auth_required(conn):
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[len("Bearer "):].strip()
    user = auth.resolve_token(conn, token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    auth.touch_last_seen(conn, user["id"])
    auth.log_access(conn, user["id"], request.method, request.url.path)
    return user


def require_market(market: str):
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"неизвестный market '{market}', допустимо: {list(MARKETS)}")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/whoami")
def whoami(request: Request, authorization: Optional[str] = Header(None)):
    """Кто я, по мнению сервера — фронтенд показывает это в шапке, чтобы
    приглашённый человек видел, под каким именем он вошёл."""
    user = check_auth(request, authorization)
    return {"name": user["name"] if user else None, "auth_required": auth.auth_required(dbmod.get_conn())}


@app.get("/api/markets")
def get_markets(request: Request, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    return [{"id": k, "label": v["label"]} for k, v in MARKETS.items()]


@app.get("/api/symbols")
def get_symbols(request: Request, market: str = Query(...), authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    require_market(market)

    cached = _symbols_cache.get(market)
    if cached and (time.time() - cached[0]) < SYMBOLS_CACHE_TTL:
        return cached[1]

    http = RateLimitedSession()
    try:
        symbols = list_symbols(http, market, log=lambda _: None)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"не удалось получить список символов с биржи: {exc}")
    _symbols_cache[market] = (time.time(), symbols)
    return symbols


@app.get("/api/summary")
def get_summary(request: Request, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    conn = dbmod.get_conn()
    return {
        "markets": dbmod.get_summary(conn),
        "db_file_size_bytes": dbmod.get_db_file_size(),
    }


@app.get("/api/gaps")
def get_gaps(request: Request, market: str, symbol: str, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    require_market(market)
    conn = dbmod.get_conn()
    return dbmod.get_gaps(conn, market, symbol)


@app.post("/api/jobs")
def start_job(request: Request, market: str = Query(...), symbol: str = Query(...), authorization: Optional[str] = Header(None)):
    user = check_auth(request, authorization)
    require_market(market)
    started_by = user["name"] if user else None
    try:
        job = jobsmod.manager.start(market, symbol, started_by=started_by)
    except jobsmod.JobLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return job.to_dict()


@app.get("/api/jobs")
def list_jobs(request: Request, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    active = [j.to_dict() for j in jobsmod.manager.list()]
    conn = dbmod.get_conn()
    history = dbmod.list_jobs_log(conn)
    return {"active": active, "history": history}


@app.get("/api/jobs/{job_id}")
def get_job(request: Request, job_id: str, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    job = jobsmod.manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job не найден")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: str, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    ok = jobsmod.manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="job не запущен или не найден")
    return {"cancelled": True}


@app.get("/api/jobs/{job_id}/stream")
def stream_job(request: Request, job_id: str, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    job = jobsmod.manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job не найден")

    def event_gen():
        sent = 0
        while True:
            lines = job.log[sent:]
            for line in lines:
                yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
            sent += len(lines)
            yield f"data: {json.dumps({'type': 'status', **job.to_dict()})}\n\n"
            if job.status != "running":
                break
            time.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _load_range_df(conn, market: str, symbol: str, start_ms: Optional[int], end_ms: Optional[int]) -> pd.DataFrame:
    q = "SELECT open_time, open, high, low, close, volume FROM klines WHERE market=? AND symbol=?"
    params = [market, symbol]
    if start_ms is not None:
        q += " AND open_time >= ?"
        params.append(start_ms)
    if end_ms is not None:
        q += " AND open_time <= ?"
        params.append(end_ms)
    q += " ORDER BY open_time"
    rows = conn.execute(q, params).fetchall()
    if not rows:
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("dt")


def _resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe not in VIEW_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"неизвестный timeframe '{timeframe}', допустимо: {list(VIEW_TIMEFRAMES)}")
    if df.empty:
        return df
    rule = VIEW_TIMEFRAMES[timeframe]
    out = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna(subset=["open"])
    return out


@app.get("/api/data/preview")
def data_preview(
    request: Request,
    market: str, symbol: str, timeframe: str = "1h",
    start: Optional[int] = None, end: Optional[int] = None, limit: int = 1000,
    authorization: Optional[str] = Header(None),
):
    check_auth(request, authorization)
    require_market(market)
    conn = dbmod.get_conn()
    df = _load_range_df(conn, market, symbol, start, end)
    df = _resample(df, timeframe)
    if len(df) > limit:
        df = df.tail(limit)
    return [
        {"time": int(idx.timestamp()), "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}
        for idx, r in df.iterrows()
    ]


@app.get("/api/data/export")
def data_export(
    request: Request,
    market: str, symbol: str, timeframe: str = "1h",
    start: Optional[int] = None, end: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    check_auth(request, authorization)
    require_market(market)
    conn = dbmod.get_conn()
    df = _load_range_df(conn, market, symbol, start, end)
    df = _resample(df, timeframe)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["open_time_utc", "open", "high", "low", "close", "volume"])
    for idx, r in df.iterrows():
        writer.writerow([idx.isoformat(), r.open, r.high, r.low, r.close, r.volume])
    buf.seek(0)

    filename = f"{market}_{symbol}_{timeframe}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/data/download-db")
def download_db(request: Request, authorization: Optional[str] = Header(None)):
    check_auth(request, authorization)
    return FileResponse(DB_PATH, filename="market_data.db", media_type="application/octet-stream")
