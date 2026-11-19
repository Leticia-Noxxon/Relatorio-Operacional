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


def import_rounded_excel(history: dict, path: Path) -> dict:
    """Casa IDs arredondados pelo Excel e só acrescenta envios realmente novos."""
    import csv as csv_mod
    from datetime import datetime

    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12,
    }

    def parse_minute(text: str) -> datetime | None:
        text = (text or "").strip()
        if not text:
            return None
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", text)
        if match:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)), int(match.group(4) or 0), int(match.group(5) or 0))
        match = re.search(
            r"(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(\d{1,2}),\s*(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
            text,
            re.I,
        )
        if match:
            return datetime(int(match.group(3)), months[match.group(1).lower()], int(match.group(2)), int(match.group(4) or 0), int(match.group(5) or 0))
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", text)
        if match:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4) or 0), int(match.group(5) or 0))
        return None

    def pref(value: str) -> str:
        text = str(value or "").strip()
        return text[:-2] if text.endswith(".0") else text

    def garage(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    known = []
    for key, row in history.get("records", {}).items():
        try:
            exact = int(str(row.get("ID do Envio")).split(".")[0])
        except (TypeError, ValueError):
            continue
        if str(key).startswith("xls:"):
            continue
        known.append({
            "id": exact,
            "pref": pref(row.get("Prefixo")),
            "minute": parse_minute(str(row.get("Data") or "")) or parse_minute(str(row.get("Data de Envio") or "")),
            "garage": garage(row.get("Garagem")),
        })

    stats = {
        "matched_id": 0,
        "matched_prefix": 0,
        "added": 0,
        "ambiguous": [],
        "prefix_ties_resolved_by_id": [],
    }
    with path.open(encoding="utf-8", newline="") as handle:
        incoming = list(csv_mod.DictReader(handle))
    for raw in incoming:
        token = str(raw.get("ID do Envio") or "").strip()
        try:
            rounded = int(token) if token.isdigit() else int(float(token))
        except (TypeError, ValueError):
            stats["ambiguous"].append({"reason": "id ilegível", "prefixo": raw.get("Prefixo")})
            continue
        minute = parse_minute(raw.get("Data") or "") or parse_minute(raw.get("Data de Envio") or "")
        prefix = pref(raw.get("Prefixo"))
        this_garage = garage(raw.get("Garagem"))
        id_hits = [item for item in known if abs(item["id"] - rounded) <= 1024]
        prefix_hits = [
            item for item in known
            if prefix and minute and item["pref"] == prefix and item["minute"] == minute
        ]
        if len(id_hits) > 1 or (not id_hits and len(prefix_hits) > 1):
            stats["ambiguous"].append({
                "rounded_id": rounded,
                "prefixo": prefix,
                "data": minute.isoformat(sep=" ") if minute else "",
                "id_hits": len(id_hits),
                "prefix_hits": len(prefix_hits),
            })
            continue
        if id_hits:
            hit = id_hits[0]
            if prefix and hit["pref"] and hit["pref"] != prefix:
                stats["ambiguous"].append({"rounded_id": rounded, "reason": "prefixo diverge", "prefixo": prefix})
                continue
            if this_garage and hit["garage"] and hit["garage"] != this_garage:
                stats["ambiguous"].append({"rounded_id": rounded, "reason": "garagem diverge"})
                continue
            if len(prefix_hits) > 1:
                stats["prefix_ties_resolved_by_id"].append({
                    "rounded_id": rounded,
                    "prefixo": prefix,
                    "data": minute.isoformat(sep=" ") if minute else "",
                    "prefix_hits": len(prefix_hits),
                })
            stats["matched_id"] += 1
            continue
        if len(prefix_hits) == 1:
            hit = prefix_hits[0]
            if this_garage and hit["garage"] and hit["garage"] != this_garage:
                stats["ambiguous"].append({"rounded_id": rounded, "reason": "garagem diverge no prefixo+minuto"})
                continue
            stats["matched_prefix"] += 1
            continue
        mapped = row_from_export(raw)
        mapped["ID do Envio"] = str(rounded)
        mapped["id_aproximado"] = True
        key = f"xls:{rounded}"
        if key in history["records"]:
            stats["matched_id"] += 1
            continue
        history["records"][key] = clean_row(mapped)
        stats["added"] += 1
    return stats


def main() -> int:
    onedrive = IMPORT_DIR / "revisao_cftv_onedrive.csv"
    extra = IMPORT_DIR / "revisao_cftv_downloads_extra.csv"
    history = load_history()
    before = len(history.get("records") or {})
    added_one, skip_one = add_missing(history, [row_from_onedrive(row) for row in read_csv(onedrive)])
    added_extra, skip_extra = add_missing(history, [row_from_export(row) for row in read_csv(extra)])
    rounded_path = IMPORT_DIR / "revisao_cftv_export_2026-11-19.csv"
    rounded_stats = {"matched_id": 0, "matched_prefix": 0, "added": 0, "ambiguous": []}
    if rounded_path.is_file():
        rounded_stats = import_rounded_excel(history, rounded_path)
        print(
            "excel_arredondado",
            f"casados_id={rounded_stats['matched_id']}",
            f"casados_prefixo_minuto={rounded_stats['matched_prefix']}",
            f"novos={rounded_stats['added']}",
            f"ambiguos={len(rounded_stats['ambiguous'])}",
            f"empates_prefixo_resolvidos_por_id={len(rounded_stats['prefix_ties_resolved_by_id'])}",
        )
        for item in rounded_stats["ambiguous"]:
            print("ambiguo", item)
        for item in rounded_stats["prefix_ties_resolved_by_id"]:
            print("empate_prefixo_resolvido", item)
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
