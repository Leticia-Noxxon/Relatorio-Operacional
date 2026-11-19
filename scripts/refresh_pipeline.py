#!/usr/bin/env python3
"""Pipeline completo: Jotform + NxNet + regeneração dos relatórios."""

from __future__ import annotations

import argparse
import json
import os
import re
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


def configure_period(start: date, end: date) -> None:
    """O período entra por variável de ambiente. Os scripts não são reescritos."""
    os.environ["REPORT_PERIOD_START"] = start.isoformat()
    os.environ["REPORT_PERIOD_END"] = end.isoformat()
    print(f"periodo {start.isoformat()} .. {end.isoformat()}")


def require_secrets() -> None:
    missing = [
        name
        for name in ("NOXXON_PASSWORD", "JOTFORM_API_KEY")
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        print(
            "Segredos ausentes: " + ", ".join(missing) + ". "
            "Nenhum JSON do painel será alterado.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def run_optional(cmd: list[str], label: str, detail: dict) -> None:
    try:
        run(cmd)
        detail["steps"].append(label)
    except subprocess.CalledProcessError as exc:
        detail.setdefault("warnings", []).append(f"{label} exit {exc.returncode}")
        print(f"WARN {label} não bloqueia o JSON do painel", file=sys.stderr)


def write_status(ok: bool, detail: dict) -> None:
    now = datetime.now(TZ)
    payload = {
        "ok": ok,
        "updated_at": now.isoformat(),
        "updated_at_label": now.strftime("%d/%m/%Y %H:%M"),
        "start": detail.get("start"),
        "end": detail.get("end"),
        "running": False,
        "message": None if ok else "Falha na atualização",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("status", payload["updated_at_label"], "ok=", ok)


def assert_published_datasets() -> None:
    """Recusa publicar JSON vazio por cima do último dado bom."""
    root = ROOT / "web" / "data" / "datasets"
    checks = {
        "executivo": lambda d: int((d.get("kpis") or {}).get("maintenances") or 0) >= 1690,
        "santa": lambda d: bool(d.get("prefixes")),
        "sdcard": lambda d: int((d.get("kpis") or {}).get("total_cards") or 0) > 0,
        "conexao": lambda d: bool(d.get("all"))
        or int((d.get("totais") or {}).get("unidades") or 0) > 0,
        "retorno": lambda d: int(d.get("trocas") or 0) > 0 or bool(d.get("rows")),
    }
    for name, check in checks.items():
        path = root / f"{name}.json"
        if not path.is_file() or path.stat().st_size < 20:
            raise RuntimeError(f"dataset ausente ou vazio: {path.name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not check(data):
            raise RuntimeError(f"dataset sem dados utilizáveis: {path.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-05")
    ap.add_argument("--end", default=datetime.now(TZ).date().isoformat())
    ap.add_argument("--skip-collect", action="store_true")
    args = ap.parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        print("Período inválido: fim anterior ao início", file=sys.stderr)
        return 2

    detail: dict = {"start": args.start, "end": args.end, "steps": []}
    try:
        if not args.skip_collect:
            require_secrets()
        configure_period(start, end)
        if not args.skip_collect:
            run([sys.executable, "scripts/collect_jotform.py"])
            detail["steps"].append("jotform")
            run([sys.executable, "scripts/collect_status_api.py"])
            detail["steps"].append("nxnet_historico")
            run([sys.executable, "scripts/collect_conexao.py"])
            detail["steps"].append("nxnet_conexao")

        run_optional([sys.executable, "generate_report.py"], "pdf_executivo", detail)
        run_optional(
            [sys.executable, "scripts/generate_status_pdfs.py"],
            "pdf_status",
            detail,
        )
        run_optional(
            [sys.executable, "scripts/generate_conexao_pdf.py"],
            "pdf_conexao",
            detail,
        )
        retorno_src = ROOT / "data" / "relatorios" / "offline_apos_troca_switch_old.tsv"
        if retorno_src.is_file():
            run([sys.executable, "scripts/generate_retorno_switch.py"])
            detail["steps"].append("retorno")
        else:
            detail.setdefault("warnings", []).append("retorno_source_absent")
            print(
                "WARN fonte de retorno ausente; JSON de retorno anterior permanece",
                file=sys.stderr,
            )
        run_optional(
            [sys.executable, "scripts/apply_pptx_template.py"],
            "pptx",
            detail,
        )

        run_optional(
            [
                sys.executable,
                "-c",
                "import fitz; from pathlib import Path\n"
                "OUT=Path('reports/previews'); OUT.mkdir(parents=True, exist_ok=True)\n"
                "pdfs=['relatorio_executivo_cftv','CFTV_Santa_Brigida','Analise_SDCard_Metropole_Expandir',"
                "'Conexao_Cameras_por_Unidade','Retorno_Falhas_Switches_CFTV']\n"
                "for stem in pdfs:\n"
                " p=Path('reports')/f'{stem}.pdf'\n"
                " if not p.exists():\n"
                "  print(stem, 'sem pdf'); continue\n"
                " doc=fitz.open(p)\n"
                " for i,page in enumerate(doc,1):\n"
                "  page.get_pixmap(matrix=fitz.Matrix(1.4,1.4), alpha=False).save(OUT/f'{stem}_p{i}.png')\n"
                " doc.close(); print(stem, 'ok')\n",
            ],
            "previews",
            detail,
        )
        run([sys.executable, "scripts/export_web_data.py"])
        detail["steps"].append("web_json")
        assert_published_datasets()

        # Espelha artefatos para o app Next (web/public)
        web_reports = ROOT / "web" / "public" / "reports"
        web_previews = ROOT / "web" / "public" / "previews"
        web_status = ROOT / "web" / "data" / "web_status.json"
        if (ROOT / "web").exists():
            web_reports.mkdir(parents=True, exist_ok=True)
            web_previews.mkdir(parents=True, exist_ok=True)
            published_pdfs = ROOT / "web" / "public" / "pdfs"
            published_pdfs.mkdir(parents=True, exist_ok=True)
            for pdf in (ROOT / "reports").glob("*.pdf"):
                (web_reports / pdf.name).write_bytes(pdf.read_bytes())
                (published_pdfs / pdf.name).write_bytes(pdf.read_bytes())
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
        print("ERRO", _safe_error(exc), file=sys.stderr)
        print("JSON do painel não será publicado.", file=sys.stderr)
        return 1


def _safe_error(exc: BaseException) -> str:
    raw = str(exc)
    if re.search(r"(apiKey|api_key|senha|password|st)=", raw, re.I):
        return type(exc).__name__
    return f"{type(exc).__name__}: {raw[:300]}"


if __name__ == "__main__":
    raise SystemExit(main())
