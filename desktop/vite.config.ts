import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_TARGET = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [".."],
    },
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: {
      // Same paths the React client calls with `VITE_API_BASE` unset in dev (same-origin relative URLs).
      "/health": { target: API_TARGET, changeOrigin: true },
      "/assumptions": { target: API_TARGET, changeOrigin: true },
      "/workbooks": { target: API_TARGET, changeOrigin: true },
      "/model": { target: API_TARGET, changeOrigin: true },
      "/optimization": { target: API_TARGET, changeOrigin: true },
      "/exports": { target: API_TARGET, changeOrigin: true },
    },
  },
});
