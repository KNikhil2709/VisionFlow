import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the FastAPI backend. In dev we proxy /api and /data to
// it so the browser makes same-origin requests (no CORS surprises).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/data": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
