import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true — слушать на 0.0.0.0, чтобы страница была доступна не только
// с localhost (нужно для Tailscale/доступа с других устройств, см. README).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: true,
    port: 4173,
  },
});
