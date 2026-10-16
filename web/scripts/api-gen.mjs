#!/usr/bin/env node
/**
 * OpenAPI → orval generation — 24-frontend-arxitekturasi.md §3, 32-kod-qoidalari.md §6.2 / §7.5 (gate 5).
 *
 *   pnpm api:gen          regenerate from the committed packages/shared/api/openapi.json
 *   pnpm api:fetch        download http://localhost:8000/api/v1/openapi.json (or $ERP_OPENAPI_URL) first
 *   pnpm api:export       export the schema from ../backend without running it (uv + app factory)
 *   pnpm api:check        regenerate and fail if generated code differs from git (schema drift)
 */
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = join(root, "packages", "shared", "api");
const schemaPath = join(apiDir, "openapi.json");
const generatedDirs = ["packages/shared/api/src/generated", "packages/shared/models/src/generated"];

const args = new Set(process.argv.slice(2));

async function fetchSchema() {
  const url = process.env.ERP_OPENAPI_URL || "http://localhost:8000/api/v1/openapi.json";
  process.stdout.write(`Fetching ${url}\n`);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET ${url} → HTTP ${response.status}`);
  const schema = await response.json();
  writeFileSync(schemaPath, `${JSON.stringify(schema, null, 2)}\n`);
  process.stdout.write(`Wrote ${schemaPath}\n`);
}

/** Backend not running: build the FastAPI app via its factory and dump app.openapi() (no DB/Redis needed). */
function exportSchema() {
  const backendDir = join(root, "..", "backend");
  const code = [
    "import json, sys",
    "from app.main import create_app",
    "sys.stdout.write(json.dumps(create_app().openapi()))",
  ].join("; ");
  const out = execFileSync("uv", ["run", "python", "-c", code], {
    cwd: backendDir,
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  // json.dumps is ASCII-only (safe through Windows console code pages); re-serialise as UTF-8 here.
  writeFileSync(schemaPath, `${JSON.stringify(JSON.parse(out), null, 2)}\n`);
  process.stdout.write(`Exported backend schema → ${schemaPath}\n`);
}

function run(cmd, cmdArgs, cwd) {
  execFileSync(cmd, cmdArgs, { cwd, stdio: "inherit", shell: process.platform === "win32" });
}

function checkSchema() {
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
  if (!schema.openapi || !schema.paths) throw new Error(`${schemaPath} is not an OpenAPI document`);
}

/** orval imports schemas by relative path across packages; rewrite to the package export. */
function rewriteModelImports(dir) {
  for (const name of readdirSync(dir)) {
    const file = join(dir, name);
    if (statSync(file).isDirectory()) {
      rewriteModelImports(file);
    } else if (file.endsWith(".ts")) {
      const source = readFileSync(file, "utf8");
      const next = source.replace(/from '(?:\.\.\/)+models\/src\/generated'/g, "from '@shared/models/generated'");
      if (next !== source) writeFileSync(file, next);
    }
  }
}

async function main() {
  if (args.has("--fetch")) await fetchSchema();
  if (args.has("--export")) exportSchema();
  checkSchema();
  run("pnpm", ["exec", "orval", "--config", "orval.config.ts"], apiDir);
  rewriteModelImports(join(apiDir, "src", "generated"));

  if (args.has("--check")) {
    const status = execFileSync("git", ["status", "--porcelain", "--", ...generatedDirs], {
      cwd: root,
      encoding: "utf8",
    });
    if (status.trim().length > 0) {
      process.stderr.write(
        `\nOpenAPI ↔ orval drift: generated client differs from the committed version.\n${status}\n` +
          "Run `pnpm api:gen` and commit the result.\n",
      );
      process.exit(1);
    }
    process.stdout.write("api:check — generated client is up to date.\n");
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
