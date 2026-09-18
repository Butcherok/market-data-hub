"""
Персональные токены доступа + журнал обращений (кто/когда/какой эндпоинт).

Пока в таблице users нет ни одной записи — поведение как раньше (запросы не
требуют авторизации, доступ ограничивается только сетью: Tailscale/localhost).
Как только появляется первый пользователь (создаётся через manage_users.py,
включая самого владельца) — ВСЕ /api/* запросы от ВСЕХ, включая владельца,
начинают требовать валидный персональный Bearer-токен.

Токены хранятся только в виде SHA-256 хэша — сам токен нигде на диске не
лежит в открытом виде (кроме момента создания, когда его нужно один раз
показать и передать человеку).
"""
import hashlib
import secrets
import time
import uuid


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def auth_required(conn) -> bool:
    """True, если в системе есть хотя бы один активный (не отозванный) пользователь."""
    row = conn.execute("SELECT COUNT(*) FROM users WHERE revoked_at IS NULL").fetchone()
    return row[0] > 0


def create_user(conn, name: str) -> tuple[str, str]:
    """Создаёт пользователя, возвращает (user_id, raw_token). raw_token показывается
    один раз — дальше восстановить его нельзя, только выдать новый (revoke + add)."""
    user_id = uuid.uuid4().hex[:10]
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO users (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
        (user_id, name, _hash(token), int(time.time() * 1000)),
    )
    conn.commit()
    return user_id, token


def resolve_token(conn, token: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, revoked_at FROM users WHERE token_hash=?",
        (_hash(token),),
    ).fetchone()
    if not row or row["revoked_at"] is not None:
        return None
    return {"id": row["id"], "name": row["name"]}


def touch_last_seen(conn, user_id: str):
    conn.execute("UPDATE users SET last_seen_at=? WHERE id=?", (int(time.time() * 1000), user_id))
    conn.commit()


def log_access(conn, user_id: str | None, method: str, path: str):
    conn.execute(
        "INSERT INTO access_log (user_id, method, path, ts) VALUES (?, ?, ?, ?)",
        (user_id, method, path, int(time.time() * 1000)),
    )
    conn.commit()


def list_users(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, created_at, last_seen_at, revoked_at FROM users ORDER BY created_at"
    ).fetchall()
    return [dict(r) for r in rows]


def revoke_user(conn, user_id: str) -> bool:
    cur = conn.execute(
        "UPDATE users SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
        (int(time.time() * 1000), user_id),
    )
    conn.commit()
    return cur.rowcount > 0
