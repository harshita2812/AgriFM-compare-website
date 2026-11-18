import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  expect: { timeout: 7000 },
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.AGRIFM_BASE_URL || "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
});
