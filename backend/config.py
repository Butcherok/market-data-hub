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
SYMBOLS_CACHE_TTL_SECONDS = 300

# Авторизация — персональные токены (см. auth.py / manage_users.py), не общий
# секрет. Пока в БД нет ни одного пользователя, API открыт (рассчитано на то, что
# доступ и так ограничен сетью — localhost/Tailscale). Старый MARKET_DATA_AUTH_TOKEN
# (общий секрет на всех) снят — см. README, раздел про публикацию.

# CORS: домен(ы), с которых разрешено обращаться к API. Не задан — разрешено
# всё (allow_origins=["*"]), это нормально для localhost/Tailscale (сеть уже закрыта),
# но НЕДОПУСТИМО при публикации через Cloudflare Tunnel/ngrok — там обязательно
# указать точный публичный адрес фронтенда.
# Пример: MARKET_DATA_ALLOWED_ORIGIN=https://data.example.com
ALLOWED_ORIGIN = os.environ.get("MARKET_DATA_ALLOWED_ORIGIN")
