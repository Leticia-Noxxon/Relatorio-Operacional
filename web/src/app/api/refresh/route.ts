import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Desabilitado: app público não executa pipeline nem coleta externa. */
export async function POST() {
  return NextResponse.json(
    { ok: false, error: "Atualização não disponível." },
    { status: 404 },
  );
}

export async function GET() {
  return NextResponse.json(
    { ok: false, error: "Atualização não disponível." },
    { status: 404 },
  );
}
