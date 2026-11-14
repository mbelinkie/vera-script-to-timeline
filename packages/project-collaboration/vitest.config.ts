import { defineConfig } from "vitest/config";

// The in-memory PostgreSQL used by these tests takes a few seconds to start.
export default defineConfig({ test: { testTimeout: 30_000, hookTimeout: 30_000 } });
