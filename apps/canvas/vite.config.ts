import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // GitHub project pages serve from /<repo-name>/ — set CANVAS_BASE there.
  // Local dev/preview and truth-guard keep the default "/".
  base: process.env.CANVAS_BASE ?? "/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
