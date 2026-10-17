import { writeFileSync } from "node:fs";

import { NGINX_NONCE, parseLanPrinterOrigins, securityHeaders } from "../csp.ts";

import { nginxSecurityHeaders } from "./render.ts";

// 24 §6.1 / §4.4: LAN HTTP printer origins of this deployment (deploy config), none by default.
const lanPrinterOrigins = parseLanPrinterOrigins(process.env.ERP_CSP_LAN_PRINTERS);

writeFileSync(
  new URL("./nginx-security-headers.conf", import.meta.url),
  nginxSecurityHeaders(
    securityHeaders({ nonce: null, lanPrinterOrigins }),
    securityHeaders({ nonce: NGINX_NONCE, lanPrinterOrigins }),
  ),
);
