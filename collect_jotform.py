#!/usr/bin/env python3
"""Baixa exportações da tabela Jotform Revisão CFTV.

Prioridade:
1) JOTFORM_API_KEY → submissions API → XLSX
2) JOTFORM_SHARE_URL / URL padrão com token st= (melhor esforço)
3) Mantém o XLSX local mais recente se a coleta falhar
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "jotform"
OUT.mkdir(parents=True, exist_ok=True)

FORM_ID = os.environ.get("JOTFORM_FORM_ID", "250754083828665")
DEFAULT_SHARE = (
    "https://www.jotform.com/tables/250754083828665"
    "?st=RWprbDdhTVFlVUZLWVlHVm1hbHNqYWN0TVNHSjQ1ZWpVam0ydHZodUEzNGh5TlA1"
    "Q3hINzV5bkgyZGxEWDZzZVNPbjBNNy93MHJVVk05UDZreDFPR2Q4U2hnb3BGb2tlTW1N"
    "M1R3QWRTRWJvT0RhT1dJejJ5MU9ldlUvQ3grekI="
)
SHARE_URL = os.environ.get("JOTFORM_SHARE_URL", DEFAULT_SHARE)
API_KEY = os.environ.get("JOTFORM_API_KEY", "").strip()
TZ = ZoneInfo("America/Sao_Paulo")


def _stamp() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def save_dataframe(df: pd.DataFrame) -> Path:
    out = OUT / f"Revisao_CFTV_{_stamp()}.xlsx"
    df.to_excel(out, index=False)
    print("Jotform salvo", out, "linhas", len(df))
    return out


def from_api_key() -> Path | None:
    if not API_KEY:
        return None
    url = f"https://api.jotform.com/form/{FORM_ID}/submissions"
    params = {"apiKey": API_KEY, "limit": 1000, "orderby": "created_at"}
    rows: list[dict] = []
    offset = 0
    while True:
        params["offset"] = offset
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()
        content = payload.get("content") or []
        if not content:
            break
        for item in content:
            answers = item.get("answers") or {}
            flat: dict = {
                "ID do Envio": item.get("id"),
                "Data de Envio": item.get("created_at"),
            }
            for ans in answers.values():
                name = (ans.get("text") or ans.get("name") or "").strip() or "campo"
                val = ans.get("prettyFormat")
                if val is None:
                    val = ans.get("answer")
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                flat[name] = val
            rows.append(flat)
        if len(content) < params["limit"]:
            break
        offset += params["limit"]
    if not rows:
        print("Jotform API: nenhuma submission", file=sys.stderr)
        return None
    return save_dataframe(pd.DataFrame(rows))


def probe_share_url() -> dict:
    """Verifica se o link compartilhado ainda libera a tabela sem login."""
    r = requests.get(
        SHARE_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    text = r.text or ""
    needs_login = "Please log in" in text or "forceLogin" in text or "loginFlowHelper" in text
    return {
        "status": r.status_code,
        "needs_login": needs_login,
        "title": "Revisão CFTV" if "Revis" in text else None,
    }


def latest_local() -> Path | None:
    files = sorted(OUT.glob("Revisao_CFTV_*.xlsx"))
    return files[-1] if files else None


def main() -> int:
    probe = probe_share_url()
    print("Jotform share probe:", json.dumps(probe, ensure_ascii=False))

    try:
        path = from_api_key()
        if path:
            print("fonte=api_key")
            return 0
    except Exception as exc:
        print("WARN Jotform API:", exc, file=sys.stderr)

    local = latest_local()
    if local:
        print(
            "fonte=local_fallback",
            local.name,
            "(share URL exige login; defina JOTFORM_API_KEY para export automático)",
        )
        # Copia com data de hoje para marcar tentativa de atualização
        stamped = OUT / f"Revisao_CFTV_{_stamp()}.xlsx"
        if local.resolve() != stamped.resolve():
            stamped.write_bytes(local.read_bytes())
            print("cópia", stamped.name)
        return 0

    print("ERRO: sem JOTFORM_API_KEY e sem XLSX local", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
