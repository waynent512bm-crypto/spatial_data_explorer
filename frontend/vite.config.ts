import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = process.env.SDE_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Same-origin /api in dev, so the backend needs no CORS setup.
    proxy: { "/api": backend },
  },
});
