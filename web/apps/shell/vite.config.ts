/**
 * apps/shell — the single Vite application (24 §1): router, layouts, auth provider.
 *
 * - Manrope is bundled from @fontsource-variable/manrope (24 §4.1): only latin, latin-ext, cyrillic,
 *   cyrillic-ext are emitted; the latin subset is preloaded; all four are precached by the PWA.
 * - PWA via vite-plugin-pwa (24 Asosiy xulosa #6); registerSW is an external script (CSP-safe).
 * - Strict CSP meta in the built index.html + full security headers on `vite preview` (csp.ts); the
 *   style nonce placeholder is replaced per index.html response (24 §4.4, previewCspNonce).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";
import { VitePWA } from "vite-plugin-pwa";

import { applyNonce, cspDirectives, generateNonce, securityHeaders, serializeCsp } from "./csp.ts";
import { mockApi } from "./dev/mock-api.ts";

const webRoot = fileURLToPath(new URL("../..", import.meta.url));

/** Backend paths proxied in dev/preview — same origin keeps the HttpOnly BFF cookie first-party (14 §2.1). */
const BACKEND_PATHS = ["/api", "/auth", "/oauth", "/health", "/.well-known", "/billing", "/sync"];

/** 24 §4.1: drop greek / vietnamese @font-face blocks so their files never reach dist/. */
function manropeSubsets(): Plugin {
  const unused = /\/\* manrope-(?:greek|vietnamese)-wght-normal \*\/\s*@font-face\s*\{[^}]*\}/g;
  return {
    name: "erp-manrope-subsets",
    enforce: "pre",
    transform(code, id) {
      if (!id.includes("@fontsource-variable") || !id.split("?")[0]?.endsWith(".css")) return null;
      return { code: code.replace(unused, ""), map: null };
    },
  };
}

/** 24 §4.1: `<link rel="preload">` for the hashed latin subset file. */
function fontPreload(): Plugin {
  let base = "/";
  return {
    name: "erp-font-preload",
    apply: "build",
    configResolved(config) {
      base = config.base;
    },
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const file = Object.keys(ctx.bundle ?? {}).find((f) =>
          /manrope-latin-wght-normal-[^/]+\.woff2$/.test(f),
        );
        if (!file) return [];
        return [
          {
            tag: "link",
            attrs: {
              rel: "preload",
              as: "font",
              type: "font/woff2",
              href: `${base}${file}`,
              crossorigin: "",
            },
            injectTo: "head",
          },
        ];
      },
    },
  };
}

/** qaror #57: CSP <meta> in the production index.html (headers are set by the proxy — deploy/). */
function cspMeta(agentPort: number): Plugin {
  return {
    name: "erp-csp-meta",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler() {
        return [
          {
            tag: "meta",
            attrs: {
              "http-equiv": "Content-Security-Policy",
              content: serializeCsp(cspDirectives({ agentPort }), "meta"),
            },
            injectTo: "head-prepend",
          },
        ];
      },
    },
  };
}

/**
 * 24 §4.4 on `vite preview` (the e2e server): every index.html response gets a fresh style nonce —
 * substituted in the HTML (CSP <meta>, `<meta property="csp-nonce">`) and in the CSP header — and
 * `Cache-Control: no-store`. Other files keep the static headers (preview.headers, no nonce).
 */
function previewCspNonce(agentPort: number): Plugin {
  return {
    name: "erp-preview-csp-nonce",
    configurePreviewServer(server) {
      const distDir = path.resolve(server.config.root, server.config.build.outDir);
      server.middlewares.use((req, res, next) => {
        const method = req.method ?? "GET";
        const { pathname } = new URL(req.url ?? "/", "http://preview.local");
        const isBackend = BACKEND_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
        const isDocument =
          pathname === "/index.html" ||
          (!path.posix.extname(pathname) && (req.headers.accept ?? "").includes("text/html"));
        if ((method !== "GET" && method !== "HEAD") || isBackend || !isDocument) return next();

        const nonce = generateNonce();
        const html = applyNonce(readFileSync(path.join(distDir, "index.html"), "utf8"), nonce);
        for (const [name, value] of Object.entries(securityHeaders({ agentPort, nonce }))) {
          res.setHeader(name, value);
        }
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.statusCode = 200;
        res.end(method === "HEAD" ? undefined : html);
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, webRoot, "ERP_");
  const useMock = env.ERP_API_MOCK === "1" || process.env.ERP_API_MOCK === "1";
  const apiTarget = env.ERP_DEV_API_TARGET || "http://localhost:8000";
  const agentPort = 47110;
  const proxy = Object.fromEntries(
    BACKEND_PATHS.map((path) => [path, { target: apiTarget, changeOrigin: false, secure: false }]),
  );

  return {
    envDir: webRoot,
    plugins: [
      useMock ? mockApi() : null,
      manropeSubsets(),
      react(),
      fontPreload(),
      cspMeta(agentPort),
      previewCspNonce(agentPort),
      VitePWA({
        registerType: "autoUpdate",
        injectRegister: "script",
        includeAssets: ["favicon.svg", "icons/apple-touch-icon.png"],
        manifest: {
          id: "/",
          name: "ERP — do'kon boshqaruvi",
          short_name: "ERP",
          description: "Kassa, ombor, nasiya va soliq — bitta tizimda",
          lang: "uz",
          dir: "ltr",
          start_url: "/",
          scope: "/",
          display: "standalone",
          background_color: "#F4F6F8",
          theme_color: "#0E7C66",
          icons: [
            { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
            { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          ],
        },
        workbox: {
          // 24 §4.1: the four Manrope subsets (woff2) are precached — fonts work on first offline start.
          globPatterns: ["**/*.{js,css,html,svg,png,woff2,webmanifest}"],
          globIgnores: ["**/*greek*", "**/*vietnamese*", "config.js"],
          navigateFallback: "/index.html",
          navigateFallbackDenylist: [/^\/(api|auth|oauth|health|billing|sync|\.well-known)(\/|$)/],
          cleanupOutdatedCaches: true,
          runtimeCaching: [
            {
              // Runtime config changes per environment without a rebuild → never served stale.
              urlPattern: ({ url }) => url.pathname === "/config.js",
              handler: "NetworkFirst",
              options: { cacheName: "erp-runtime-config", networkTimeoutSeconds: 3 },
            },
          ],
        },
        devOptions: { enabled: false },
      }),
    ],
    server: {
      port: 5173,
      strictPort: true,
      proxy: useMock ? undefined : proxy,
    },
    preview: {
      port: 4173,
      strictPort: true,
      // Non-HTML responses; index.html gets per-response nonce headers from previewCspNonce().
      headers: securityHeaders({ agentPort, nonce: null }),
      proxy,
    },
    build: {
      target: "es2022",
      // Everything stays a real file: no data: URIs (CSP img-src/font-src 'self').
      assetsInlineLimit: 0,
      sourcemap: "hidden",
      rolldownOptions: {
        output: {
          // Long-lived vendor chunks: app deploys do not invalidate the React runtime cache.
          codeSplitting: {
            groups: [
              { name: "react", test: /node_modules[\\/](?:react|react-dom|scheduler|react-router)[\\/]/ },
              { name: "vendor", test: /node_modules[\\/]/ },
            ],
          },
        },
      },
    },
  };
});
