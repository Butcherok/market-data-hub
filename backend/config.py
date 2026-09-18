"""
Конфигурация рынков и констант. Ничего не хардкодится сверх URL эндпоинтов —
tickSize/stepSize/MIN_NOTIONAL и список символов приходят из exchangeInfo
в рантайме (см. collector.py).
"""
import os

MARKETS = {
    "spot": {
        "label": "Spot",
        "base_url": "https://api.binance.com",
        "klines_path": "/api/v3/klines",
        "exchange_info_path": "/api/v3/exchangeInfo",
        "max_limit": 1000,
    },
    "um_futures": {
        "label": "USDⓈ-M Futures",
        "base_url": "https://fapi.binance.com",
        "klines_path": "/fapi/v1/klines",
        "exchange_info_path": "/fapi/v1/exchangeInfo",
        "max_limit": 1500,
    },
}

INTERVAL = "1m"
INTERVAL_MS = 60_000

# Таймфреймы, доступные для ПРОСМОТРА/ЭКСПОРТА (ресемплинг из хранимых 1m
# баров на лету). Сбор с биржи всегда идёт в 1m — это НЕ список того, что
# запрашивается у Binance.
VIEW_TIMEFRAMES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}

DB_PATH = os.environ.get("MARKET_DATA_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "market_data.db"))
AUTH_TOKEN = os.environ.get("MARKET_DATA_AUTH_TOKEN")  # если задан — требуется Bearer-заголовок
SYMBOLS_CACHE_TTL_SECONDS = 300
