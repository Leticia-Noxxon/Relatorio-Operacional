"""Histórico acumulado do Jotform.

O Jotform apaga envios antigos. O arquivo data/jotform/historico.json guarda
cada envio pela id (ou por uma chave composta) e nunca remove quem sumiu da API.
O agregado de 1.690 manutenções anterior ao commit 50edbd7 entra como legado:
os envios brutos daquele período não estavam no git.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "jotform" / "historico.json"
LEGACY_PERIOD_END = "2026-11-17"


def record_key(row: dict) -> str:
    sid = row.get("ID do Envio")
    text = "" if sid is None else str(sid).strip()
    if text and text.lower() not in {"none", "nan"}:
        return f"id:{text}"
    parts = [
        str(row.get("Data") or ""),
        str(row.get("Data de Envio") or ""),
        str(row.get("Prefixo") or ""),
        str(row.get("Garagem") or ""),
        str(row.get("Observações") or "")[:120],
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"ck:{digest}"


def _jsonify(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    if pd.isna(value):
        return None
    return str(value)


def clean_row(row: dict) -> dict:
    return {str(k): _jsonify(v) for k, v in row.items() if not str(k).startswith("_")}


def load_history() -> dict:
    if HISTORY_PATH.is_file():
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        data.setdefault("records", {})
        return data
    raise FileNotFoundError(f"Histórico Jotform ausente: {HISTORY_PATH}")


def save_history(data: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = HISTORY_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(HISTORY_PATH)


def merge_submissions(history: dict, rows: list[dict]) -> tuple[int, int]:
    """Acrescenta ou atualiza. Não apaga ids que a API deixou de devolver."""
    records = history.setdefault("records", {})
    added = updated = 0
    for row in rows:
        cleaned = clean_row(row)
        key = record_key(cleaned)
        if key in records:
            updated += 1
        else:
            added += 1
        records[key] = cleaned
    return added, updated


def reference_day(row: dict) -> date | None:
    from generate_report import parse_date

    for field in ("Data", "Data de Envio"):
        parsed = parse_date(row.get(field))
        if pd.notna(parsed):
            return parsed.date()
    return None


def split_against_legacy(history: dict) -> tuple[list[dict], list[dict]]:
    """Envios até o fim do legado já estão no agregado de 1.690."""
    legacy = history.get("legacy") or {}
    end = date.fromisoformat(str(legacy.get("period_end") or LEGACY_PERIOD_END))
    fresh: list[dict] = []
    duplicates: list[dict] = []
    for row in (history.get("records") or {}).values():
        day = reference_day(row)
        if day is not None and day <= end:
            duplicates.append(row)
        else:
            fresh.append(row)
    return fresh, duplicates


def records_frame(rows: list[dict], period_start: date, period_end: date) -> pd.DataFrame:
    from generate_report import parse_date

    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    if "ID do Envio" not in raw.columns:
        raw["ID do Envio"] = range(1, len(raw) + 1)
    raw["_data"] = raw.get("Data", pd.Series([None] * len(raw))).map(parse_date)
    if "Data de Envio" in raw.columns:
        raw["_envio"] = raw["Data de Envio"].map(parse_date)
    else:
        raw["_envio"] = pd.NaT
    raw["_ref"] = raw["_data"].fillna(raw["_envio"])
    period = raw[
        raw["_ref"].notna()
        & (raw["_ref"] >= pd.Timestamp(period_start))
        & (raw["_ref"] <= pd.Timestamp(f"{period_end} 23:59:59"))
    ].copy()
    if period.empty:
        return period
    period["Garagem"] = period.get("Garagem", pd.Series(index=period.index)).fillna("Não identificado").astype(str).str.strip()
    period["Prefixo"] = pd.to_numeric(period.get("Prefixo"), errors="coerce").astype("Int64")
    period["_day"] = period["_ref"].dt.date
    period["ID do Envio"] = pd.to_numeric(period["ID do Envio"], errors="coerce").fillna(0).astype(int)
    return period.reset_index(drop=True)


def _add_pairs(left, right) -> list:
    totals: dict[str, int] = {}
    for name, value in list(left or []) + list(right or []):
        totals[str(name)] = totals.get(str(name), 0) + int(value)
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def merge_executivo(legacy: dict, delta, period_end: date) -> dict:
    """Soma o agregado antigo com as manutenções posteriores ao legado."""
    out = json.loads(json.dumps(legacy))
    start = out.get("period", {}).get("start", "2026-09-05")
    end = period_end
    legacy_end = out.get("period", {}).get("end")
    if legacy_end and legacy_end > end.isoformat():
        end = date.fromisoformat(legacy_end[:10])
    out["period"] = {
        "start": start,
        "end": end.isoformat(),
        "label": f"{date.fromisoformat(start).strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}",
    }
    if delta is None or delta.n_maints == 0:
        return out

    kpis = out.setdefault("kpis", {})
    kpis["maintenances"] = int(kpis.get("maintenances") or 0) + int(delta.n_maints)
    kpis["reincidences"] = int(kpis.get("reincidences") or 0) + int(delta.n_reinc)
    kpis["prefixes"] = int(kpis.get("prefixes") or 0) + int(delta.n_prefix)
    kpis["cameras_removed"] = int(kpis.get("cameras_removed") or 0) + int(delta.n_cameras_retirada)

    garages = {g["name"]: dict(g) for g in out.get("garages") or []}
    for name, maints, reinc in delta.garage_rows:
        prefixes = int(delta.maints.loc[delta.maints["Garagem"] == name, "Prefixo"].nunique()) if len(delta.maints) else 0
        current = garages.get(name, {"name": name, "maints": 0, "reinc": 0, "prefixes": 0})
        current["maints"] = int(current.get("maints") or 0) + int(maints)
        current["reinc"] = int(current.get("reinc") or 0) + int(reinc)
        current["prefixes"] = int(current.get("prefixes") or 0) + prefixes
        garages[name] = current
    out["garages"] = sorted(garages.values(), key=lambda g: str(g["name"]).casefold())
    kpis["garages"] = len(out["garages"])

    out["problem_buckets"] = _add_pairs(out.get("problem_buckets"), delta.top_problem_buckets)
    out["action_buckets"] = _add_pairs(out.get("action_buckets"), delta.top_action_buckets)
    out["top_problems"] = _add_pairs(out.get("top_problems"), delta.top_problems)[:12]
    out["top_actions"] = _add_pairs(out.get("top_actions"), delta.top_actions)[:12]

    buckets = {item["name"]: {k: v for k, v in item.get("buckets") or []} for item in out.get("garage_bucket_problems") or []}
    for name, pairs in delta.garage_bucket_problems:
        dest = buckets.setdefault(name, {})
        for label, count in pairs:
            dest[label] = int(dest.get(label, 0)) + int(count)
    out["garage_bucket_problems"] = [
        {"name": name, "buckets": sorted(pairs.items(), key=lambda item: (-item[1], item[0]))}
        for name, pairs in sorted(buckets.items(), key=lambda item: item[0].casefold())
    ]
    return out


def build_executivo_payload(period_start: date, period_end: date) -> tuple[dict, dict]:
    from generate_report import analyze

    history = load_history()
    legacy = (history.get("legacy") or {}).get("executivo")
    fresh, duplicates = split_against_legacy(history)
    delta_df = records_frame(fresh, period_start, period_end)
    delta = analyze(delta_df) if len(delta_df) else None
    if legacy:
        payload = merge_executivo(legacy, delta, period_end)
    elif delta is not None:
        raise RuntimeError("Histórico sem legado e o exportador espera o agregado anterior.")
    else:
        raise RuntimeError("Histórico Jotform sem dados.")

    legacy_n = int((history.get("legacy") or {}).get("maintenances") or 0)
    total = int(payload["kpis"]["maintenances"])
    if legacy_n and total < legacy_n:
        raise RuntimeError(f"executivo {total} abaixo do legado {legacy_n}")
    stats = {
        "legacy": legacy_n,
        "records": len(history.get("records") or {}),
        "duplicates": len(duplicates),
        "new": int(delta.n_maints) if delta is not None else 0,
        "maintenances": total,
    }
    print(
        "jotform histórico",
        f"legado={stats['legacy']}",
        f"registros={stats['records']}",
        f"duplicatas={stats['duplicates']}",
        f"novas={stats['new']}",
        f"manutencoes={stats['maintenances']}",
    )
    return payload, stats
