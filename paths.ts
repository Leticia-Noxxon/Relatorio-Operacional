import path from "path";
import { existsSync } from "fs";

/**
 * Resolve a pasta de dados.
 * - No agent local: usa o monorepo pai (../reports, ../data, ../scripts)
 * - No app publicado: usa cópias em public/ + data/ dentro de web/
 */
function resolveRoot(): string {
  const cwd = process.cwd();
  const parent = path.resolve(cwd, "..");
  if (existsSync(path.join(parent, "scripts", "refresh_pipeline.py"))) {
    return parent;
  }
  return cwd;
}

export const ROOT = resolveRoot();
export const REPORTS_DIR = existsSync(path.join(ROOT, "reports"))
  ? path.join(ROOT, "reports")
  : path.join(process.cwd(), "public", "reports");
export const PREVIEWS_DIR = existsSync(path.join(ROOT, "reports", "previews"))
  ? path.join(ROOT, "reports", "previews")
  : path.join(process.cwd(), "public", "previews");
export const STATUS_FILE = existsSync(path.join(ROOT, "data", "web_status.json"))
  ? path.join(ROOT, "data", "web_status.json")
  : path.join(process.cwd(), "data", "web_status.json");
