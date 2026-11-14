import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// En desarrollo, /api se reenvía al API desplegado: VITE_API_PROXY=https://xxxx.execute-api.us-east-1.amazonaws.com npm run dev
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: process.env.VITE_API_PROXY
      ? { "/api": { target: process.env.VITE_API_PROXY, changeOrigin: true } }
      : undefined,
  },
  build: { chunkSizeWarningLimit: 1500 },
});
