import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true — слушаем на 0.0.0.0, чтобы страница достучалась без токена
// с localhost (нужно для Tailscale/доступа с других устройств, см. README).
//
// allowedHosts — защита Vite dev-сервера от DNS rebinding: по умолчанию
// принимает запросы только с ожидаемых хостов (localhost/IP). При публикации
// через Cloudflare Tunnel/ngrok запрос приходит с публичного домена — его
// нужно явно разрешить через переменную окружения VITE_PUBLIC_HOST (например
// VITE_PUBLIC_HOST=data.example.com), иначе Vite ответит "Blocked request.
// This host is not allowed". Не задана — поведение как раньше (только
// localhost/IP), ничего не меняется для Tailscale/локального запуска.
const allowedHosts = process.env.VITE_PUBLIC_HOST
  ? [process.env.VITE_PUBLIC_HOST]
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts,
  },
  preview: {
    host: true,
    port: 4173,
  },
});
