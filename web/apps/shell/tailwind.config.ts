import type { Config } from "tailwindcss";

import preset from "@shared/tailwind-config/preset";

/** All apps/packages use the shared preset (24 §4.3); content covers every workspace source file. */
export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../packages/shared/ui/src/**/*.{ts,tsx}",
    "../../packages/pages/*/src/**/*.{ts,tsx}",
  ],
} satisfies Config;
