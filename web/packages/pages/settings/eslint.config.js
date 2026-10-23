import { createConfig } from "@shared/eslint-config";

export default createConfig({ tsconfigRootDir: import.meta.dirname, kind: "pages" });
