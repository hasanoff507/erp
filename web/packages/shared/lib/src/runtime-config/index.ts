/**
 * Runtime configuration — 24-frontend-arxitekturasi.md §3: `window.__ERP_CONFIG__` lets one build run
 * in every environment. It is set by `/config.js` (external script, CSP-safe), loaded before the app.
 */
export interface ErpRuntimeConfig {
  /** API origin. Empty string = same origin (required for the HttpOnly BFF cookie, 14 §2.1). */
  apiBaseUrl: string;
  /** dev | test | staging | production */
  environment: "dev" | "test" | "staging" | "production";
  /** Shop agent loopback port (21 §16, default 47110). */
  agentPort: number;
}

declare global {
  interface Window {
    __ERP_CONFIG__?: Partial<ErpRuntimeConfig>;
  }
}

const DEFAULTS: ErpRuntimeConfig = {
  apiBaseUrl: "",
  environment: "dev",
  agentPort: 47110,
};

export function getRuntimeConfig(): ErpRuntimeConfig {
  const fromWindow = typeof window === "undefined" ? undefined : window.__ERP_CONFIG__;
  return { ...DEFAULTS, ...fromWindow };
}
