#!/usr/bin/env python3
"""Retorno de Falhas em Switches — CFTV.

Tempo entre a substituição do switch e o registro de uma nova falha (OFFLINE),
por prefixo. Faixas: sem falha · 1–7 · 8–15 · 16–30 · 31–60 · acima de 60 dias.
"""

from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SRC_TSV = ROOT / "data" / "relatorios" / "offline_apos_troca_switch_old.tsv"
OUT_DIR = ROOT / "data" / "relatorios"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

OUT_XLSX = OUT_DIR / "Retorno_Falhas_Switches_CFTV.xlsx"
OUT_TSV = OUT_DIR / "Retorno_Falhas_Switches_CFTV.tsv"
OUT_PDF = REPORTS / "Retorno_Falhas_Switches_CFTV.pdf"

def _env_date(name: str, default: date) -> date:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return date.fromisoformat(raw)


PERIOD_START = _env_date("REPORT_PERIOD_START", date(2026, 9, 5))
PERIOD_END = _env_date("REPORT_PERIOD_END", date(2026, 11, 17))
# Último dia com Relatório CFTV diário na base consolidada
REPORTS_END = date(2026, 10, 23)

BUCKETS = [
    "sem falha",
    "1 a 7 dias",
    "8 a 15 dias",
    "16 a 30 dias",
    "31 a 60 dias",
    "acima de 60 dias",
]

NAVY = "#1F3340"
INK = "#1F2933"
MUTED = "#5C6B73"
CARD = "#F3F5F7"
GREEN = "#7BC67E"
AMBER = "#F0C36A"
RED = "#E89A9A"

def _register_fonts() -> None:
    from font_paths import liberation_pair

    regular, bold = liberation_pair()
    pdfmetrics.registerFont(TTFont("Arial", regular))
    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))


def parse_br(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%d/%m/%Y").date()


def fmt(day: date | None) -> str:
    return day.strftime("%d/%m/%Y") if day else ""


def classify_days(days: int | None, situacao: str) -> str | None:
    """Mapeia dias/situação para as 6 faixas pedidas. None = fora do gráfico principal."""
    if days is not None:
        if 1 <= days <= 7:
            return "1 a 7 dias"
        if 8 <= days <= 15:
            return "8 a 15 dias"
        if 16 <= days <= 30:
            return "16 a 30 dias"
        if 31 <= days <= 60:
            return "31 a 60 dias"
        if days > 60:
            return "acima de 60 dias"
        # days == 0 não deve ocorrer (prazo começa no dia seguinte)
        return "1 a 7 dias"
    low = (situacao or "").casefold()
    if "sem offline" in low or "sem falha" in low:
        return "sem falha"
    # Prefixo ausente / sem linha: não entra nas 6 faixas de retorno
    return None


def load_rows() -> list[dict]:
    raw = list(csv.DictReader(SRC_TSV.open(encoding="utf-8"), delimiter="\t"))
    out = []
    for row in raw:
        swap = parse_br(row["Data da troca"])
        if swap is None or swap < PERIOD_START or swap > PERIOD_END:
            continue
        days_txt = (row.get("Dias até o OFFLINE") or "").strip()
        days = int(days_txt) if days_txt else None
        situacao = row.get("Situação") or ""
        faixa = classify_days(days, situacao)
        item = {
            "garagem": row.get("Garagem") or "",
            "nome": row.get("Nome") or "",
            "data_troca": swap,
            "prefixo": row.get("Prefixo") or "",
            "id": row.get("ID") or "",
            "data_offline": parse_br(row.get("Data do OFFLINE") or ""),
            "dias": days,
            "faixa": faixa or "",
            "situacao": situacao,
            "primeiro_relatorio": parse_br(row.get("1º relatório depois da troca") or ""),
            "dias_sem_relatorio": row.get("Dias sem relatório depois da troca") or "",
            "ja_no_primeiro": row.get("OFFLINE já no 1º relatório") or "",
            "ultimo_relatorio": parse_br(row.get("Último relatório do prefixo") or ""),
            "outra_troca": row.get("Outra troca antes do OFFLINE") or "",
            "prefixo_parecido": row.get("Prefixo parecido no relatório") or "",
            "fora_faixas": faixa is None,
        }
        # Renomeia situação de "sem offline" para "sem falha" na saída
        if item["faixa"] == "sem falha":
            item["situacao"] = f"Sem falha até {fmt(REPORTS_END)}"
        out.append(item)
    out.sort(key=lambda r: (r["data_troca"], r["prefixo"], r["nome"]))
    return out


def summarize(rows: list[dict]) -> dict:
    faixa_counts = Counter(r["faixa"] for r in rows if r["faixa"])
    fora = [r for r in rows if r["fora_faixas"]]
    com_falha = [r for r in rows if r["dias"] is not None]
    return {
        "trocas": len(rows),
        "nas_faixas": sum(faixa_counts.values()),
        "fora_faixas": len(fora),
        "com_falha": len(com_falha),
        "sem_falha": faixa_counts.get("sem falha", 0),
        "faixas": {k: faixa_counts.get(k, 0) for k in BUCKETS},
        "mediana": sorted(r["dias"] for r in com_falha)[len(com_falha) // 2] if com_falha else None,
        "media": round(sum(r["dias"] for r in com_falha) / len(com_falha), 1) if com_falha else None,
        "ja_no_primeiro": sum(1 for r in rows if (r["ja_no_primeiro"] or "").lower() == "sim"),
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "reports_end": REPORTS_END,
    }


def write_tsv(rows: list[dict]) -> None:
    headers = [
        "Garagem",
        "Nome",
        "Data da troca",
        "Prefixo",
        "ID",
        "Data da falha (OFFLINE)",
        "Dias até a falha",
        "Faixa",
        "Situação",
        "1º relatório depois da troca",
        "Dias sem relatório depois da troca",
        "OFFLINE já no 1º relatório",
        "Último relatório do prefixo",
        "Outra troca antes do OFFLINE",
    ]
    with OUT_TSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(headers)
        for r in rows:
            w.writerow(
                [
                    r["garagem"],
                    r["nome"],
                    fmt(r["data_troca"]),
                    r["prefixo"],
                    r["id"],
                    fmt(r["data_offline"]),
                    r["dias"] if r["dias"] is not None else "",
                    r["faixa"],
                    r["situacao"],
                    fmt(r["primeiro_relatorio"]),
                    r["dias_sem_relatorio"],
                    r["ja_no_primeiro"],
                    fmt(r["ultimo_relatorio"]),
                    r["outra_troca"],
                ]
            )


def write_xlsx(rows: list[dict], summary: dict) -> None:
    wb = Workbook()
    thin = Border(
        left=Side(style="thin", color="D7DEE3"),
        right=Side(style="thin", color="D7DEE3"),
        top=Side(style="thin", color="D7DEE3"),
        bottom=Side(style="thin", color="D7DEE3"),
    )
    header_fill = PatternFill("solid", fgColor="1F3340")
    header_font = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    fills = {
        "sem falha": PatternFill("solid", fgColor="C6EFCE"),
        "1 a 7 dias": PatternFill("solid", fgColor="F8CBAD"),
        "8 a 15 dias": PatternFill("solid", fgColor="FFE699"),
        "16 a 30 dias": PatternFill("solid", fgColor="BDD7EE"),
        "31 a 60 dias": PatternFill("solid", fgColor="DDEBF7"),
        "acima de 60 dias": PatternFill("solid", fgColor="E2D5F1"),
    }

    ws = wb.active
    ws.title = "Trocas"
    headers = [
        "Garagem",
        "Nome",
        "Data da troca",
        "Prefixo",
        "ID",
        "Data da falha (OFFLINE)",
        "Dias até a falha",
        "Faixa",
        "Situação",
        "1º relatório depois da troca",
        "Dias sem relatório depois da troca",
        "OFFLINE já no 1º relatório",
        "Último relatório do prefixo",
        "Outra troca antes do OFFLINE",
    ]
    ws.append(headers)
    for col, _ in enumerate(headers, start=1):
        cell = ws.cell(1, col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for r in rows:
        values = [
            r["garagem"],
            r["nome"],
            r["data_troca"],
            r["prefixo"],
            r["id"],
            r["data_offline"],
            r["dias"],
            r["faixa"],
            r["situacao"],
            r["primeiro_relatorio"],
            int(r["dias_sem_relatorio"]) if str(r["dias_sem_relatorio"]).isdigit() else r["dias_sem_relatorio"],
            r["ja_no_primeiro"],
            r["ultimo_relatorio"],
            r["outra_troca"],
        ]
        ws.append(values)
        row_idx = ws.max_row
        fill = fills.get(r["faixa"])
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row_idx, col)
            cell.border = thin
            if col in (3, 6, 10, 13) and isinstance(cell.value, date):
                cell.number_format = "DD/MM/YYYY"
            if fill and col == 8:
                cell.fill = fill
    for idx, width in enumerate([28, 28, 14, 12, 12, 16, 14, 16, 42, 16, 14, 14, 16, 16], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.auto_filter.ref = f"A1:N{ws.max_row}"
    ws.freeze_panes = "A2"

    resumo = wb.create_sheet("Resumo")
    resumo["A1"] = "Faixa"
    resumo["B1"] = "Trocas"
    resumo["D1"] = "Indicador"
    resumo["E1"] = "Valor"
    for cell in (resumo["A1"], resumo["B1"], resumo["D1"], resumo["E1"]):
        cell.fill = header_fill
        cell.font = header_font
    for i, label in enumerate(BUCKETS, start=2):
        resumo.cell(i, 1, label)
        resumo.cell(i, 2, summary["faixas"][label])
        if label in fills:
            resumo.cell(i, 1).fill = fills[label]
    indicadores = [
        ("Trocas de switch (no período)", summary["trocas"]),
        ("Com falha (OFFLINE) depois da troca", summary["com_falha"]),
        ("Sem falha até o último relatório", summary["sem_falha"]),
        ("Mediana dos dias até a falha", summary["mediana"]),
        ("Média dos dias até a falha", summary["media"]),
        ("OFFLINE já no 1º relatório seguinte", summary["ja_no_primeiro"]),
        ("Fora das faixas (sem linha / prefixo ausente)", summary["fora_faixas"]),
        ("Início do período", fmt(summary["period_start"])),
        ("Fim do período", fmt(summary["period_end"])),
        ("Último Relatório CFTV diário lido", fmt(summary["reports_end"])),
    ]
    for i, (label, value) in enumerate(indicadores, start=2):
        resumo.cell(i, 4, label)
        resumo.cell(i, 5, value)
    resumo.column_dimensions["A"].width = 18
    resumo.column_dimensions["B"].width = 10
    resumo.column_dimensions["D"].width = 48
    resumo.column_dimensions["E"].width = 18

    chart = BarChart()
    chart.type = "col"
    chart.title = "Retorno de falhas em switches por faixa"
    chart.y_axis.title = "Trocas"
    data = Reference(resumo, min_col=2, min_row=1, max_row=1 + len(BUCKETS))
    cats = Reference(resumo, min_col=1, min_row=2, max_row=1 + len(BUCKETS))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    chart.width = 18
    chart.height = 10
    resumo.add_chart(chart, "A10")

    leitura = wb.create_sheet("Leitura")
    leitura["A1"] = "Retorno de Falhas em Switches — CFTV"
    leitura["A1"].font = Font(bold=True, size=14, color="1F3340")
    notes = [
        "Tempo entre a substituição do equipamento e o registro de uma nova falha (OFFLINE), por prefixo.",
        f"Período das trocas: {fmt(PERIOD_START)} a {fmt(PERIOD_END)}.",
        f"Relatórios diários disponíveis na base: 19/01/2026 a {fmt(REPORTS_END)}.",
        "Faixas: sem falha · 1 a 7 dias · 8 a 15 dias · 16 a 30 dias · 31 a 60 dias · acima de 60 dias.",
        "Entra como falha toda linha de Relatório CFTV em que qualquer célula contém OFFLINE.",
        "O prazo começa no dia seguinte à troca (relatório do mesmo dia não entra).",
        "Dias até a falha = data do primeiro relatório com OFFLINE − data da troca.",
        "Sem falha = nenhuma linha OFFLINE depois da troca até o último relatório do prefixo.",
        "Prefixo ausente / sem linha depois da troca ficam fora do gráfico das 6 faixas.",
    ]
    for i, text in enumerate(notes, start=3):
        leitura.cell(i, 1, text)
    leitura.column_dimensions["A"].width = 110

    wb.save(OUT_XLSX)


def write_pdf(summary: dict) -> None:
    _register_fonts()
    c = canvas.Canvas(str(OUT_PDF), pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(HexColor(NAVY))
    c.rect(0, height - 52, width, 52, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 18)
    c.drawString(28, height - 34, "Retorno de Falhas em Switches — CFTV")

    y = height - 84
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 11)
    c.drawString(
        28,
        y,
        f"Tempo entre a substituição do equipamento e o registro de uma nova falha, por prefixo · "
        f"{fmt(PERIOD_START)} a {fmt(PERIOD_END)}",
    )

    # KPI cards
    cards = [
        ("Trocas", f"{summary['trocas']:,}".replace(",", ".")),
        ("Com falha", f"{summary['com_falha']:,}".replace(",", ".")),
        ("Sem falha", f"{summary['sem_falha']:,}".replace(",", ".")),
        ("Mediana (dias)", str(summary["mediana"] if summary["mediana"] is not None else "—")),
        ("Média (dias)", str(summary["media"] if summary["media"] is not None else "—")),
    ]
    card_w = (width - 56 - 16 * 4) / 5
    y = height - 150
    for i, (title, value) in enumerate(cards):
        x = 28 + i * (card_w + 16)
        c.setFillColor(HexColor(CARD))
        c.roundRect(x, y, card_w, 52, 8, fill=1, stroke=0)
        c.setFillColor(HexColor(NAVY))
        c.rect(x, y, 5, 52, fill=1, stroke=0)
        c.setFillColor(HexColor(MUTED))
        c.setFont("Arial", 9)
        c.drawString(x + 14, y + 34, title)
        c.setFillColor(HexColor(INK))
        c.setFont("Arial-Bold", 18)
        c.drawString(x + 14, y + 12, value)

    # Faixas table + bars
    y = height - 190
    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 13)
    c.drawString(28, y, "Distribuição por faixa de retorno")
    y -= 18
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 9)
    c.drawString(
        28,
        y,
        f"Base: Relatórios CFTV diários até {fmt(REPORTS_END)} · falha = OFFLINE em qualquer câmera do prefixo",
    )

    table_top = y - 16
    row_h = 28
    col_w = [180, 90, 420]
    headers = ["Faixa", "Trocas", "Proporção"]
    total = max(summary["nas_faixas"], 1)
    colors = {
        "sem falha": GREEN,
        "1 a 7 dias": RED,
        "8 a 15 dias": AMBER,
        "16 a 30 dias": "#8EB6D8",
        "31 a 60 dias": "#A9C7E0",
        "acima de 60 dias": "#C5B3DE",
    }

    x0 = 28
    for i, (h, w) in enumerate(zip(headers, col_w)):
        c.setFillColor(HexColor(NAVY))
        c.rect(x0 + sum(col_w[:i]), table_top - row_h, w, row_h, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Arial-Bold", 10)
        c.drawCentredString(x0 + sum(col_w[:i]) + w / 2, table_top - 18, h)

    y_row = table_top - row_h
    max_bar = max(summary["faixas"].values()) if summary["faixas"] else 1
    for ri, label in enumerate(BUCKETS):
        count = summary["faixas"][label]
        pct = count / total * 100
        bg = white if ri % 2 == 0 else HexColor(CARD)
        c.setFillColor(bg)
        c.rect(x0, y_row - row_h, sum(col_w), row_h, fill=1, stroke=0)
        c.setFillColor(HexColor(INK))
        c.setFont("Arial", 11)
        c.drawString(x0 + 12, y_row - 18, label)
        c.setFont("Arial-Bold", 12)
        c.drawRightString(x0 + col_w[0] + col_w[1] - 16, y_row - 18, f"{count:,}".replace(",", "."))
        # bar
        bar_x = x0 + col_w[0] + col_w[1] + 12
        bar_max_w = col_w[2] - 70
        bar_w = (count / max_bar) * bar_max_w if max_bar else 0
        c.setFillColor(HexColor(colors[label]))
        c.roundRect(bar_x, y_row - 20, max(bar_w, 0), 12, 3, fill=1, stroke=0)
        c.setFillColor(HexColor(MUTED))
        c.setFont("Arial", 10)
        c.drawString(bar_x + bar_w + 8, y_row - 18, f"{pct:.1f}%".replace(".", ","))
        y_row -= row_h

    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 8)
    c.drawString(
        28,
        28,
        "Fonte: trocas de switch (formulários/revisões) × Relatório CFTV diário · prazo a partir do dia seguinte à troca",
    )
    c.drawRightString(width - 28, 28, "1 / 1")
    c.save()


def main() -> int:
    rows = load_rows()
    summary = summarize(rows)
    write_tsv(rows)
    write_xlsx(rows, summary)
    try:
        write_pdf(summary)
    except Exception as exc:
        print("WARN PDF de retorno ignorado:", exc, file=sys.stderr)
    print("OK", OUT_XLSX)
    print("OK", OUT_TSV)
    print("OK", OUT_PDF)
    print(
        {
            "trocas": summary["trocas"],
            "faixas": summary["faixas"],
            "mediana": summary["mediana"],
            "media": summary["media"],
            "reports_end": fmt(REPORTS_END),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
