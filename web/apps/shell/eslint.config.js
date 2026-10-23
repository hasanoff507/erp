import { createConfig } from "@shared/eslint-config";

export default createConfig({
  tsconfigRootDir: import.meta.dirname,
  kind: "app",
  ignores: ["public/**"],
  projects: ["./tsconfig.json", "./tsconfig.node.json"],
});
