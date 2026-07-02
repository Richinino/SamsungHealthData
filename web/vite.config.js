import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base './' aby index.html fungoval aj keď ho servuje FastAPI z /web/dist
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
