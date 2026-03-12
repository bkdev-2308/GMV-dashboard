import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/admin/login": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/admin/logout": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/logout": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/login": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/brand/logout": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      // "/static": {
      //   target: "http://localhost:4000",
      //   changeOrigin: true,
      // },
    },
  },
});
