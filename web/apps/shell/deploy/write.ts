import { writeFileSync } from "node:fs";

import { NGINX_NONCE, securityHeaders } from "../csp.ts";

import { nginxSecurityHeaders } from "./render.ts";

writeFileSync(
  new URL("./nginx-security-headers.conf", import.meta.url),
  nginxSecurityHeaders(securityHeaders({ nonce: null }), securityHeaders({ nonce: NGINX_NONCE })),
);
