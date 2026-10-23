import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // IndexedDB for Dexie in Node — must be installed before Dexie is imported.
    setupFiles: ["fake-indexeddb/auto"],
  },
});
