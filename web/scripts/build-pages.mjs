/**
 * Static export for GitHub Pages.
 *
 * Sets GITHUB_PAGES so next.config enables output:'export' and basePath.
 * Route handlers cannot be exported (dynamic params, POST, force-dynamic),
 * so src/app/api is moved aside for this build only and restored afterwards.
 * Datasets are copied into public/data for the static host, then removed.
 */
import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  renameSync,
  rmSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = path.join(webRoot, "src", "app", "api");
const apiBak = path.resolve(webRoot, "..", ".pages-api-backup");
const publicDir = path.join(webRoot, "public");
const publicData = path.join(publicDir, "data");

function restoreApi() {
  if (!existsSync(apiBak)) return;
  if (existsSync(apiDir)) rmSync(apiDir, { recursive: true, force: true });
  renameSync(apiBak, apiDir);
}

if (existsSync(apiBak) && !existsSync(apiDir)) {
  restoreApi();
}

process.env.GITHUB_PAGES = "true";
process.env.NEXT_PUBLIC_GITHUB_PAGES = "true";
process.env.NEXT_PUBLIC_BASE_PATH = "/Relatorio-Operacional";

const createdPublic = !existsSync(publicDir);
let code = 1;
let moved = false;

try {
  if (!existsSync(apiDir)) {
    console.error("API routes not found at", apiDir);
    process.exit(1);
  }

  rmSync(apiBak, { recursive: true, force: true });
  renameSync(apiDir, apiBak);
  moved = true;

  mkdirSync(path.join(publicData, "datasets"), { recursive: true });
  cpSync(path.join(webRoot, "data", "datasets"), path.join(publicData, "datasets"), {
    recursive: true,
  });
  cpSync(
    path.join(webRoot, "data", "web_status.json"),
    path.join(publicData, "web_status.json"),
  );

  const result = spawnSync("npm", ["run", "build"], {
    cwd: webRoot,
    stdio: "inherit",
    env: process.env,
  });
  code = result.status === null ? 1 : result.status;
} finally {
  if (moved) {
    try {
      restoreApi();
    } catch (err) {
      console.error("Failed to restore API routes:", err);
      code = 1;
    }
  }
  rmSync(publicData, { recursive: true, force: true });
  if (createdPublic) {
    rmSync(publicDir, { recursive: true, force: true });
  }
}

process.exit(code);
