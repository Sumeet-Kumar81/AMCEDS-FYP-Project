import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Port 5173 is in the backend's CORS_ORIGINS (.env). strictPort: fail instead of moving to another port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
});
