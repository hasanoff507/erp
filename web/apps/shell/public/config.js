/*
 * Runtime configuration (24-frontend-arxitekturasi.md §3) — replaced per environment at deploy time;
 * one build runs everywhere. Not precached by the service worker (always fetched NetworkFirst).
 * apiBaseUrl must stay "" (same origin): the HttpOnly BFF session cookie is first-party only.
 */
window.__ERP_CONFIG__ = {
  apiBaseUrl: "",
  environment: "dev",
  agentPort: 47110,
};
