import { NextResponse } from "next/server";
import { getReport } from "@/lib/reports";

export const dynamic = "force-dynamic";

/** Prévia de PDF desabilitada no app publicado. */
export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string; page: string }> },
) {
  const { id } = await context.params;
  if (!getReport(id)) {
    return NextResponse.json({ error: "Relatório inválido" }, { status: 404 });
  }
  return NextResponse.json(
    { error: "Prévia desabilitada neste ambiente." },
    { status: 404 },
  );
}
