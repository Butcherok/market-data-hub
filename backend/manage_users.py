"""
[ADMIN CLI] — управление персональными токенами доступа к Market Data Hub.

Запускать ТОЛЬКО ЛОКАЛЬНО, на том ПК, где лежит backend/data/market_data.db.
Это не HTTP-эндпоинт и не должно им становиться — управление пользователями
через публичный интерфейс не предусмотрено намеренно (меньше поверхность
атаки).

Пока в базе нет ни одного пользователя — API работает в старом режиме, без
авторизации (доступ ограничен только сетью — Tailscale/localhost). Как
только создан первый пользователь (в том числе для себя самого) — API
требует персональный Bearer-токен от каждого, включая владельца.

Использование:
    python manage_users.py add "Имя"        — создать пользователя, вывести токен + готовую ссылку
    python manage_users.py list             — список пользователей, последний визит, статус
    python manage_users.py revoke <user_id> — отозвать токен (человек теряет доступ немедленно)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth
import db as dbmod


def cmd_add(name: str):
    conn = dbmod.get_conn()
    user_id, token = auth.create_user(conn, name)
    print(f"Пользователь создан: {name} (id={user_id})")
    print(f"Токен (показывается один раз, сохрани): {token}")
    print()
    print("Ссылка для этого человека (подставь свой реальный адрес вместо HOST):")
    print(f"  https://HOST/?token={token}")
    print()
    print("Токен сам впишется в браузер при первом переходе по ссылке и останется там же.")


def cmd_list():
    conn = dbmod.get_conn()
    rows = auth.list_users(conn)
    if not rows:
        print("Пользователей нет — API работает без авторизации (доступ ограничен только сетью).")
        return
    for r in rows:
        last = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(r["last_seen_at"] / 1000))
            if r["last_seen_at"]
            else "никогда"
        )
        status = "ОТОЗВАН" if r["revoked_at"] else "активен"
        print(f"{r['id']}  {r['name']:<20} {status:<8} последний визит: {last}")


def cmd_revoke(user_id: str):
    conn = dbmod.get_conn()
    ok = auth.revoke_user(conn, user_id)
    print("Отозван." if ok else "Пользователь с таким id не найден (или уже отозван).")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, *rest = sys.argv[1:]
    if cmd == "add" and rest:
        cmd_add(rest[0])
    elif cmd == "list":
        cmd_list()
    elif cmd == "revoke" and rest:
        cmd_revoke(rest[0])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
