import { promises as fs } from "fs";
import { NextResponse } from "next/server";
import { STATUS_FILE } from "@/lib/paths";
import { isRefreshRunning } from "@/lib/refresh-lock";
import { REPORTS } from "@/lib/reports";

export const dynamic = "force-dynamic";

const PUBLIC_KEYS = [
  "ok",
  "updated_at",
  "updated_at_label",
  "start",
  "end",
  "running",
  "message",
] as const;

function publicStatus(raw: Record<string, unknown>) {
  const out: Record<string, unknown> = { ok: true };
  for (const key of PUBLIC_KEYS) {
    if (key in raw) out[key] = raw[key];
  }
  // Nunca expor logs, caminhos ou detalhes internos.
  delete out.last_log_tail;
  delete out.steps;
  delete out.log;
  return out;
}

export async function GET() {
  let status: Record<string, unknown> = {
    ok: true,
    updated_at_label: "—",
    start: "2026-09-05",
    end: new Date().toISOString().slice(0, 10),
    running: false,
    message: null,
  };
  try {
    const raw = JSON.parse(await fs.readFile(STATUS_FILE, "utf8")) as Record<
      string,
      unknown
    >;
    status = { ...status, ...raw };
  } catch {
    /* seed ausente */
  }

  if (status.running && !isRefreshRunning()) {
    status = { ...status, running: false, message: null };
  } else if (isRefreshRunning()) {
    status = { ...status, running: true };
  }

  const reports = REPORTS.map((r) => ({
    id: r.id,
    title: r.title,
    short: r.short,
    // PDFs/prévias não são servidos no app público.
    pdfOk: false,
    pages: 0,
  }));

  return NextResponse.json({ ...publicStatus(status), reports });
}
