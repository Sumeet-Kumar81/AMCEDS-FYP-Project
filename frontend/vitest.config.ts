import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["shared/src/**/*.test.{ts,tsx}", "dashboard/src/**/*.test.{ts,tsx}", "pwa/src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
