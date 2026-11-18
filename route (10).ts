import { promises as fs } from "fs";
import { NextResponse } from "next/server";
import path from "path";
import { existsSync } from "fs";
import { ROOT } from "@/lib/paths";
import { getReport } from "@/lib/reports";

export const dynamic = "force-dynamic";

/**
 * Datasets do painel público são agregados/anonimizados em data/datasets
 * (sem nomes de pessoas, IDs de operadora ou prefixos reais).
 */
function dataPath(id: string): string {
  const serverOnly = path.join(process.cwd(), "data", "datasets", `${id}.json`);
  const monorepo = path.join(ROOT, "data", "web", `${id}.json`);
  if (existsSync(serverOnly)) return serverOnly;
  return monorepo;
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  if (!getReport(id)) {
    return NextResponse.json({ error: "Relatório inválido" }, { status: 404 });
  }
  try {
    const raw = await fs.readFile(dataPath(id), "utf8");
    const payload = JSON.parse(raw) as unknown;
    return NextResponse.json(payload, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: "Dados ainda não exportados." },
      { status: 404 },
    );
  }
}
