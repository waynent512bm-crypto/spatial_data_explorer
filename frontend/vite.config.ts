import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = process.env.SDE_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Fail loudly instead of silently moving to 5174 while an old server still holds 5173.
    strictPort: true,
    // Same-origin /api in dev, so the backend needs no CORS setup.
    proxy: { "/api": backend },
  },
});
