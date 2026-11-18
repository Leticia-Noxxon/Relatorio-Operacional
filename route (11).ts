import { NextResponse } from "next/server";
import { getReport } from "@/lib/reports";

export const dynamic = "force-dynamic";

/** PDFs não são servidos no app publicado (dados operacionais / PII). */
export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  if (!getReport(id)) {
    return NextResponse.json({ error: "Relatório inválido" }, { status: 404 });
  }
  return NextResponse.json(
    { error: "Download de PDF desabilitado neste ambiente." },
    { status: 404 },
  );
}
