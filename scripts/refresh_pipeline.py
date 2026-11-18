#!/usr/bin/env python3
"""Pipeline completo: Jotform + NxNet + regeneração dos relatórios."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "web_status.json"
TZ = ZoneInfo("America/Sao_Paulo")


def run(cmd: list[str], env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged.setdefault("PYTHONUNBUFFERED", "1")
    subprocess.run(cmd, cwd=str(ROOT), check=True, env=merged)


def patch_period(start: date, end: date) -> None:
    """Ajusta PERIOD_END / fim de coleta nos scripts principais."""
    replacements = {
        ROOT / "generate_report.py": (
            "PERIOD_END = date(",
            f"PERIOD_END = date({end.year}, {end.month}, {end.day})",
        ),
        ROOT / "scripts" / "generate_retorno_switch.py": (
            "PERIOD_END = date(",
            f"PERIOD_END = date({end.year}, {end.month}, {end.day})",
        ),
    }
    for path, (prefix, new_line) in replacements.items():
        text = path.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines(True):
            if line.lstrip().startswith(prefix):
                indent = line[: len(line) - len(line.lstrip())]
                lines.append(indent + new_line + "\n")
            else:
                lines.append(line)
        path.write_text("".join(lines), encoding="utf-8")

    # coleta NxNet: historico até end (ou end-1 se for hoje incompleto)
    collect = ROOT / "scripts" / "collect_status_api.py"
    text = collect.read_text(encoding="utf-8")
    # substitui ambos os fim= date(...)
    import re

    text2, n = re.subn(
        r'"fim": date\(\d+, \d+, \d+\)',
        f'"fim": date({end.year}, {end.month}, {end.day})',
        text,
    )
    if n:
        collect.write_text(text2, encoding="utf-8")
        print(f"collect fim -> {end} ({n} ocorrências)")

    # PERIOD_START opcional
    if start:
        for path in (ROOT / "generate_report.py", ROOT / "scripts" / "generate_retorno_switch.py"):
            t = path.read_text(encoding="utf-8")
            lines = []
            for line in t.splitlines(True):
                if line.lstrip().startswith("PERIOD_START = date("):
                    indent = line[: len(line) - len(line.lstrip())]
                    lines.append(
                        f"{indent}PERIOD_START = date({start.year}, {start.month}, {start.day})\n"
                    )
                else:
                    lines.append(line)
            path.write_text("".join(lines), encoding="utf-8")


def write_status(ok: bool, detail: dict) -> None:
    now = datetime.now(TZ)
    payload = {
        "ok": ok,
        "updated_at": now.isoformat(),
        "updated_at_label": now.strftime("%d/%m/%Y %H:%M"),
        **detail,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("status", payload["updated_at_label"], "ok=", ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-05")
    ap.add_argument("--end", default=datetime.now(TZ).date().isoformat())
    ap.add_argument("--skip-collect", action="store_true")
    args = ap.parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    detail: dict = {"start": args.start, "end": args.end, "steps": []}
    try:
        patch_period(start, end)
        if not args.skip_collect:
            run([sys.executable, "scripts/collect_jotform.py"])
            detail["steps"].append("jotform")
            run([sys.executable, "scripts/collect_status_api.py"])
            detail["steps"].append("nxnet_historico")
            run([sys.executable, "scripts/collect_conexao.py"])
            detail["steps"].append("nxnet_conexao")

        run([sys.executable, "generate_report.py"])
        run([sys.executable, "scripts/generate_status_pdfs.py"])
        run([sys.executable, "scripts/generate_conexao_pdf.py"])
        run([sys.executable, "scripts/generate_retorno_switch.py"])
        try:
            run([sys.executable, "scripts/apply_pptx_template.py"])
        except subprocess.CalledProcessError as exc:
            detail["pptx_warn"] = str(exc)
        detail["steps"].append("generate")

        # previews
        run(
            [
                sys.executable,
                "-c",
                "import fitz; from pathlib import Path\n"
                "OUT=Path('reports/previews'); OUT.mkdir(exist_ok=True)\n"
                "pdfs=['relatorio_executivo_cftv','CFTV_Santa_Brigida','Analise_SDCard_Metropole_Expandir',"
                "'Conexao_Cameras_por_Unidade','Retorno_Falhas_Switches_CFTV']\n"
                "for stem in pdfs:\n"
                " p=Path('reports')/f'{stem}.pdf'\n"
                " if not p.exists(): continue\n"
                " doc=fitz.open(p)\n"
                " for i,page in enumerate(doc,1):\n"
                "  page.get_pixmap(matrix=fitz.Matrix(1.4,1.4), alpha=False).save(OUT/f'{stem}_p{i}.png')\n"
                " doc.close(); print(stem, 'ok')\n",
            ]
        )
        detail["steps"].append("previews")
        run([sys.executable, "scripts/export_web_data.py"])
        detail["steps"].append("web_json")

        # Espelha artefatos para o app Next (web/public)
        web_reports = ROOT / "web" / "public" / "reports"
        web_previews = ROOT / "web" / "public" / "previews"
        web_status = ROOT / "web" / "data" / "web_status.json"
        if (ROOT / "web").exists():
            web_reports.mkdir(parents=True, exist_ok=True)
            web_previews.mkdir(parents=True, exist_ok=True)
            for pdf in (ROOT / "reports").glob("*.pdf"):
                (web_reports / pdf.name).write_bytes(pdf.read_bytes())
            for png in (ROOT / "reports" / "previews").glob("*.png"):
                (web_previews / png.name).write_bytes(png.read_bytes())
            if STATUS.exists():
                web_status.parent.mkdir(parents=True, exist_ok=True)
                web_status.write_bytes(STATUS.read_bytes())
            detail["steps"].append("sync_web_public")

        write_status(True, detail)
        # re-sync status after final write
        if (ROOT / "web").exists() and STATUS.exists():
            web_status.parent.mkdir(parents=True, exist_ok=True)
            web_status.write_bytes(STATUS.read_bytes())
        return 0
    except Exception as exc:
        detail["error"] = str(exc)
        write_status(False, detail)
        print("ERRO", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
