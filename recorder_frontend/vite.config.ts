import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/rec/",
  plugins: [svelte(), svelteTesting()],
  build: {
    outDir: "../app/recorder_dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api/v1": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    setupFiles: ["./src/test-setup.ts"],
  },
});
