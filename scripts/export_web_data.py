#!/usr/bin/env python3
"""Exporta JSON dos relatórios para o painel web (UI online, não PDF)."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

OUT = ROOT / "data" / "web"
OUT.mkdir(parents=True, exist_ok=True)

from generate_report import PERIOD_END, PERIOD_START, analyze, load_maintenances  # noqa: E402
from generate_status_pdfs import (  # noqa: E402
    _day_has_cameras,
    analyze_sd,
    cameras_for_prefix,
    cell_status_sd,
    load_job,
    parse_day,
    pick_latest,
    pref_day_status,
    prefix_start_map,
)


MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def dump(name: str, payload: dict) -> None:
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Servidor-only (não colocar em public/ — arquivos estáticos seriam baixáveis sem auth)
    web_data = ROOT / "web" / "data" / "datasets"
    web_data.mkdir(parents=True, exist_ok=True)
    (web_data / f"{name}.json").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print("OK", path)


def export_executivo() -> None:
    report = analyze(load_maintenances())
    dump(
        "executivo",
        {
            "period": {
                "start": PERIOD_START.isoformat(),
                "end": PERIOD_END.isoformat(),
                "label": f"{PERIOD_START.strftime('%d/%m')} a {PERIOD_END.strftime('%d/%m/%Y')}",
            },
            "kpis": {
                "maintenances": report.n_maints,
                "reincidences": report.n_reinc,
                "prefixes": report.n_prefix,
                "garages": report.n_garages,
                "cameras_removed": report.n_cameras_retirada,
            },
            "problem_buckets": report.top_problem_buckets,
            "action_buckets": report.top_action_buckets,
            "top_problems": report.top_problems[:12],
            "top_actions": report.top_actions[:12],
            "garages": [
                {
                    "name": g,
                    "maints": n,
                    "reinc": r,
                    "prefixes": int(
                        report.maints.loc[
                            report.maints["Garagem"] == g, "Prefixo"
                        ].nunique()
                    ),
                }
                for g, n, r in report.garage_rows
            ],
            "garage_bucket_problems": [
                {"name": g, "buckets": buckets} for g, buckets in report.garage_bucket_problems
            ],
        },
    )


def export_santa() -> None:
    santa = load_job(pick_latest("santa_brigida_*.json"))
    starts = prefix_start_map(santa)
    prefixos = sorted(santa["prefixos_alvo"], key=lambda p: (starts.get(p, date.min), str(p)))
    days = sorted(d for d, b in santa["dias"].items() if _day_has_cameras(b))

    stats = {}
    for pref in prefixos:
        ok = bad = 0
        for day in days:
            st = pref_day_status(santa, pref, day, starts)
            if st == "ok":
                ok += 1
            elif st == "bad":
                bad += 1
        tot = ok + bad
        stats[pref] = {
            "ok": ok,
            "bad": bad,
            "total": tot,
            "pct_ok": round(ok / tot * 100, 1) if tot else 0,
            "pct_bad": round(bad / tot * 100, 1) if tot else 0,
        }

    months = []
    for month in sorted({parse_day(d).month for d in days}):
        mdays = [d for d in days if parse_day(d).month == month]
        ok = bad = 0
        grid = []
        for day in mdays:
            row = {"day": day, "label": parse_day(day).strftime("%d/%m"), "cells": {}}
            for pref in prefixos:
                st = pref_day_status(santa, pref, day, starts)
                row["cells"][pref] = st
                if st == "ok":
                    ok += 1
                elif st == "bad":
                    bad += 1
            grid.append(row)
        tot = ok + bad
        months.append(
            {
                "month": month,
                "name": MONTH_NAMES.get(month, str(month)),
                "start": mdays[0],
                "end": mdays[-1],
                "label": f"{MONTH_NAMES.get(month)} ({parse_day(mdays[0]).strftime('%d/%m')} a {parse_day(mdays[-1]).strftime('%d/%m')})",
                "ok": ok,
                "bad": bad,
                "availability": round(ok / tot * 100, 1) if tot else 0,
                "days": [parse_day(d).strftime("%d/%m") for d in mdays],
                "grid": [
                    {
                        "day": g["label"],
                        "cells": [g["cells"].get(p, "na") for p in prefixos],
                    }
                    for g in grid
                ],
            }
        )

    dump(
        "santa",
        {
            "period": {
                "start": days[0],
                "end": days[-1],
                "label": f"{parse_day(days[0]).strftime('%d/%m/%Y')} a {parse_day(days[-1]).strftime('%d/%m/%Y')}",
            },
            "prefixes": prefixos,
            "stats": stats,
            "months": months,
        },
    )


def export_sdcard() -> None:
    metro = load_job(pick_latest("metropole_expandir_*.json"))
    prefixos = list(metro["prefixos_alvo"])
    stats = analyze_sd(metro, prefixos)
    days = stats["days"]

    months = []
    for month in sorted({parse_day(d).month for d in days}):
        mdays = [d for d in days if parse_day(d).month == month]
        day_index = {d: i for i, d in enumerate(days)}
        rows = []
        for pref in prefixos:
            cams = cameras_for_prefix(metro, pref) or [21, 22, 23]
            for cam in cams:
                seq_full = stats["statuses"].get((pref, cam), ["off"] * len(days))
                seq = [seq_full[day_index[d]] for d in mdays]
                rows.append({"prefixo": pref, "camera": cam, "seq": seq})
        months.append(
            {
                "month": month,
                "name": MONTH_NAMES.get(month, str(month)),
                "label": f"{MONTH_NAMES.get(month)} ({parse_day(mdays[0]).strftime('%d/%m')} a {parse_day(mdays[-1]).strftime('%d/%m')})",
                "days": [parse_day(d).strftime("%d/%m") for d in mdays],
                "rows": rows,
            }
        )

    dump(
        "sdcard",
        {
            "period": {
                "start": days[0],
                "end": days[-1],
                "label": f"{parse_day(days[0]).strftime('%d/%m')} a {parse_day(days[-1]).strftime('%d/%m/%Y')}",
            },
            "kpis": {
                "prefixes": len(prefixos),
                "total_cards": stats["total_cards"],
                "ok": stats["n_ok"],
                "erro": stats["n_err"],
                "offline": stats["n_off"],
                "pct_ok": round(stats["n_ok"] / max(stats["total_cards"], 1) * 100, 1),
                "pct_erro": round(stats["n_err"] / max(stats["total_cards"], 1) * 100, 1),
            },
            "problems": stats["problems"][:20],
            "months": months,
        },
    )


def export_conexao() -> None:
    path = ROOT / "data" / "status_cameras" / "conexao_cameras_resumo.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("rows") or []
    all_rows = sorted(rows, key=lambda r: (-int(r.get("veiculos_problema") or 0), r.get("unidade") or ""))
    metro = [r for r in all_rows if r.get("metropole")]
    dump(
        "conexao",
        {
            "coletado_em": raw.get("coletado_em"),
            "totais": {
                "veiculos_problema": sum(int(r.get("veiculos_problema") or 0) for r in rows),
                "cameras_problema": sum(int(r.get("cameras_problema") or 0) for r in rows),
                # veiculos_erro_sd vem do collect; fallback: no máximo 1 SD por câmera com erro
                "veiculos_erro_sd": sum(
                    int(
                        r.get("veiculos_erro_sd")
                        if r.get("veiculos_erro_sd") is not None
                        else min(
                            int(r.get("camera_erro_sd") or 0),
                            int(r.get("veiculos_problema") or 0) or int(r.get("camera_erro_sd") or 0),
                        )
                    )
                    for r in rows
                ),
                "cameras_erro_sd": sum(int(r.get("camera_erro_sd") or 0) for r in rows),
                "unidades": len(rows),
            },
            "all": all_rows,
            "metropole": metro,
        },
    )


def export_retorno() -> None:
    tsv = ROOT / "data" / "relatorios" / "Retorno_Falhas_Switches_CFTV.tsv"
    rows = list(csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t"))
    faixas = Counter((r.get("Faixa") or "").strip() for r in rows)
    order = [
        "sem falha",
        "1 a 7 dias",
        "8 a 15 dias",
        "16 a 30 dias",
        "31 a 60 dias",
        "acima de 60 dias",
    ]
    buckets = [{"name": k, "count": faixas.get(k, 0)} for k in order]
    dias = []
    for r in rows:
        try:
            dias.append(int(r.get("Dias até a falha") or ""))
        except ValueError:
            pass
    # Painel web público: não exportar nome de pessoa nem campos auxiliares sensíveis.
    safe_cols = [
        "Garagem",
        "Data da troca",
        "Prefixo",
        "Data da falha (OFFLINE)",
        "Dias até a falha",
        "Faixa",
        "Situação",
    ]
    safe_rows = [{k: (r.get(k) or "") for k in safe_cols} for r in rows[:200]]
    dump(
        "retorno",
        {
            "trocas": len(rows),
            "buckets": buckets,
            "mediana": sorted(dias)[len(dias) // 2] if dias else None,
            "media": round(sum(dias) / len(dias), 1) if dias else None,
            "rows": safe_rows,
        },
    )


def main() -> int:
    export_executivo()
    export_santa()
    export_sdcard()
    export_conexao()
    export_retorno()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
