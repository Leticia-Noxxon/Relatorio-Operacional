/** Lê resposta como JSON; se vier HTML (login/gate), devolve erro claro. */
export async function readJson<T = unknown>(
  res: Response,
): Promise<{ ok: true; data: T } | { ok: false; error: string; status: number }> {
  const text = await res.text();
  const trimmed = text.trim();
  if (
    trimmed.startsWith("<!DOCTYPE") ||
    trimmed.startsWith("<!doctype") ||
    trimmed.startsWith("<html")
  ) {
    return {
      ok: false,
      status: res.status,
      error:
        "Não foi possível carregar os dados (resposta inválida do servidor). Tente novamente ou peça acesso ao administrador.",
    };
  }
  try {
    return { ok: true, data: JSON.parse(text) as T };
  } catch {
    return {
      ok: false,
      status: res.status,
      error: `Resposta inválida da API (${res.status}).`,
    };
  }
}
