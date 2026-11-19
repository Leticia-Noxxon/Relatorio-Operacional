#!/usr/bin/env python3
"""Importa os CSV da Revisão CFTV para data/jotform/historico.json.

Os envios que já estão no histórico (coleta da API) não são sobrescritos.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from generate_report import ACT_MAP, PROB_MAP  # noqa: E402
from jotform_history import (  # noqa: E402
    HISTORY_PATH,
    clean_row,
    load_history,
    record_key,
    save_history,
)

IMPORT_DIR = ROOT / "data" / "jotform" / "import"

PROBLEM_FIELDS = {
    "problemasDetectados": "Problemas Detectados: Câm. Frontal",
    "problemasDetectados135": "Problemas Detectados: Câm. Frente",
    "problemasDetectados138": "Problemas Detectados: Câm. Corredor 1",
    "problemasDetectados140": "Problemas Detectados: Câm. Corredor 2",
    "problemasDetectados142": "Problemas Detectados: Câm. Corredor 3",
    "problemasDetectados144": "Problemas Detectados: Câm. Corredor 4",
}
ACTION_FIELDS = {
    "acoesCamera": "Ações: Câm. Frontal",
    "acoesCam136": "Ações: Câm. Frente",
    "acoesCam139": "Ações: Câm. Corredor 1",
    "acoesCam141": "Ações: Câm. Corredor 2",
    "acoesCam145": "Ações: Câm. Corredor 3",
    "acoesCam146": "Ações: Câm. Corredor 4",
}

CANONICAL = sorted(
    set(PROB_MAP) | set(PROB_MAP.values()) | set(ACT_MAP) | set(ACT_MAP.values())
    | {
        "A2 Transportes",
        "Alfa Rodobus",
        "Alfa Rodobus SPE",
        "Santa Brigida",
        "Santa Brígida",
        "Via Sudeste Cursino",
        "Via Sudeste Sapopemba",
        "Viação Grajaú",
        "Viação Metrópole AE Carvalho",
        "Viação Metrópole Brás",
        "Viação Metrópole Iguatemi",
        "Viação Metrópole Imperador",
        "Viação Metrópole Itaim",
        "Viação Metrópole M'Boi Mirim",
        "Viação Metrópole Pinedo",
        "Nenhuma anomalia identificada",
        "Nenhuma ação realizada",
    },
    key=len,
    reverse=True,
)


def _squash(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.replace("�", "")
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def repair_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw or "�" not in raw:
        return raw
    parts = re.split(r"�+", raw)
    if len(parts) == 1:
        return raw
    pattern = re.compile("^" + ".*".join(re.escape(part) for part in parts) + "$", re.I)
    matches = [item for item in CANONICAL if pattern.search(item)]
    if len(matches) == 1:
        return matches[0]
    target = _squash(raw)
    squash_hits = [item for item in CANONICAL if _squash(item) == target]
    if len(squash_hits) == 1:
        return squash_hits[0]
    if matches:
        return min(matches, key=lambda item: abs(len(item) - len(raw)))
    return raw


def repair_list(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    pieces = [repair_text(part.strip()) for part in re.split(r"[,;]\s*", text)]
    return ", ".join(piece for piece in pieces if piece)


def blank(value: str) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def row_from_onedrive(raw: dict) -> dict:
    out = {
        "ID do Envio": blank(raw.get("submission_id")),
        "Data de Envio": blank(raw.get("created_at")),
        "Data": blank(raw.get("data")) or blank(raw.get("created_at")),
        "Garagem": repair_text(blank(raw.get("garagem"))),
        "Prefixo": blank(raw.get("prefixo")) or blank(raw.get("prefixo_132")),
        "Nome": repair_text(blank(raw.get("nome156")) or blank(raw.get("tecnico"))),
        "Tecnologia": repair_text(blank(raw.get("tecnologia"))),
        "Switch Utilizado": blank(raw.get("switchUtilizado")),
        "Cartão de Memória Utilizado": blank(raw.get("cartaoDe")),
        "Observações": repair_list(blank(raw.get("observacao"))),
    }
    for source, target in PROBLEM_FIELDS.items():
        out[target] = repair_list(blank(raw.get(source)))
    for source, target in ACTION_FIELDS.items():
        out[target] = repair_list(blank(raw.get(source)))
    return out


def row_from_export(raw: dict) -> dict:
    out = {
        "ID do Envio": blank(raw.get("ID do Envio")),
        "Data de Envio": blank(raw.get("Data de Envio")),
        "Data": blank(raw.get("Data")) or blank(raw.get("Data de Envio")),
        "Garagem": repair_text(blank(raw.get("Garagem"))),
        "Prefixo": blank(raw.get("Prefixo")),
        "Nome": repair_text(blank(raw.get("Nome"))),
        "Tecnologia": repair_text(blank(raw.get("Tecnologia"))),
        "Switch Utilizado": blank(raw.get("Switch Utilizado")),
        "Cartão de Memória Utilizado": blank(raw.get("Cartão de Memória Utilizado")),
        "Observações": repair_list(blank(raw.get("Observações"))),
        "Câmera Utilizada": blank(raw.get("Câmera Utilizada")),
    }
    for key, value in raw.items():
        if key.startswith("Problemas Detectados") or key.startswith("Ações"):
            out[key] = repair_list(blank(value))
    return out


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def add_missing(history: dict, rows: list[dict]) -> tuple[int, int]:
    records = history.setdefault("records", {})
    added = skipped = 0
    for row in rows:
        cleaned = clean_row(row)
        key = record_key(cleaned)
        if not key.startswith("id:"):
            continue
        if key in records:
            skipped += 1
            continue
        records[key] = cleaned
        added += 1
    return added, skipped


def main() -> int:
    onedrive = IMPORT_DIR / "revisao_cftv_onedrive.csv"
    extra = IMPORT_DIR / "revisao_cftv_downloads_extra.csv"
    history = load_history()
    before = len(history.get("records") or {})
    added_one, skip_one = add_missing(history, [row_from_onedrive(row) for row in read_csv(onedrive)])
    added_extra, skip_extra = add_missing(history, [row_from_export(row) for row in read_csv(extra)])
    history.pop("legacy", None)
    save_history(history)
    from datetime import date

    from jotform_history import build_executivo_payload

    payload, _stats = build_executivo_payload(date(2026, 9, 5), date(2026, 11, 19))
    history = load_history()
    history["baseline_maintenances"] = int(payload["kpis"]["maintenances"])
    history.pop("legacy", None)
    save_history(history)
    print("baseline_manutencoes", history["baseline_maintenances"])
    broken = sum(
        1
        for row in history["records"].values()
        if "�" in " ".join(str(value or "") for value in row.values())
    )
    print(
        "historico",
        f"antes={before}",
        f"onedrive_novos={added_one}",
        f"onedrive_ja_existiam={skip_one}",
        f"extra_novos={added_extra}",
        f"extra_ja_existiam={skip_extra}",
        f"total={len(history['records'])}",
        f"ainda_com_replacement={broken}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
