import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 개발 중 백엔드 API 호출을 8000 포트로 프록시
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
