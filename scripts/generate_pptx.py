#!/usr/bin/env python3
"""Gera PowerPoints 100% editáveis dos relatórios CFTV (sem imagens)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATA = ROOT / "data" / "status_cameras"
OUT = REPORTS / "pptx"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

NAVY = RGBColor(0x1F, 0x33, 0x40)
MUTED = RGBColor(0x5C, 0x6B, 0x73)
INK = RGBColor(0x1F, 0x29, 0x33)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CARD = RGBColor(0xF3, 0xF5, 0xF7)
GREEN = RGBColor(0x7B, 0xC6, 0x7E)
RED = RGBColor(0xE8, 0x9A, 0x9A)
GRAY = RGBColor(0xC5, 0xCE, 0xD6)
OFF_BG = RGBColor(0xD9, 0xDE, 0xE3)


def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def set_run(run, text: str, size: int, bold: bool = False, color: RGBColor = INK):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Arial"


def add_rect(slide, left, top, width, height, fill: RGBColor):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def add_text(slide, left, top, width, height, text: str, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    set_run(p.add_run(), text, size, bold, color)
    return box


def title_bar(slide, title: str, subtitle: str | None = None):
    h = Inches(0.72) if subtitle else Inches(0.58)
    add_rect(slide, Inches(0), Inches(0), SLIDE_W, h, NAVY)
    box = slide.shapes.add_textbox(Inches(0.35), Inches(0.12), Inches(12.6), h - Inches(0.1))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    set_run(p.add_run(), title, 20, True, WHITE)
    if subtitle:
        p2 = tf.add_paragraph()
        set_run(p2.add_run(), subtitle, 11, False, WHITE)
    return h + Inches(0.12)


def kpi_card(slide, left, top, width, height, label: str, value: str):
    add_rect(slide, left, top, width, height, CARD)
    box = slide.shapes.add_textbox(left + Inches(0.12), top + Inches(0.1), width - Inches(0.24), height - Inches(0.16))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    set_run(tf.paragraphs[0].add_run(), label, 10, True, MUTED)
    p2 = tf.add_paragraph()
    set_run(p2.add_run(), value, 18, True, NAVY)


def style_cell(cell, text: str, *, size=10, bold=False, fill: RGBColor | None = None, font_color: RGBColor = INK, align=PP_ALIGN.LEFT):
    cell.text = ""
    tf = cell.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    set_run(p.add_run(), text, size, bold, font_color)
    if fill is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill


def add_table(
    slide,
    left,
    top,
    width,
    height,
    rows: list[list[str]],
    col_widths: list[float] | None = None,
    *,
    font_size: int = 10,
    header=True,
):
    n_rows = len(rows)
    n_cols = len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = shape.table
    if col_widths:
        total = sum(col_widths)
        for i, w in enumerate(col_widths):
            table.columns[i].width = int(width * (w / total))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            is_header = header and r == 0
            fill = NAVY if is_header else (CARD if r % 2 == 0 else WHITE)
            color = WHITE if is_header else INK
            style_cell(
                table.cell(r, c),
                str(val),
                size=font_size + (1 if is_header else 0),
                bold=is_header,
                fill=fill,
                font_color=color,
                align=PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT,
            )
    return shape


def add_heatmap_table(
    slide,
    left,
    top,
    width,
    height,
    header_row: list[str],
    body: list[list[tuple[str, RGBColor | None]]],
    *,
    font_size: int = 7,
    label_cols: int = 2,
):
    """Tabela editável: cada célula = (texto, cor de fundo)."""
    rows_data = [header_row] + [[cell[0] for cell in row] for row in body]
    n_rows = len(rows_data)
    n_cols = len(header_row)
    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = shape.table

    # larguras: labels mais largos, dias iguais
    label_share = 0.14 if label_cols == 2 else 0.10
    day_share = (1.0 - label_share) / max(n_cols - label_cols, 1)
    for i in range(n_cols):
        if i < label_cols:
            table.columns[i].width = int(width * (label_share / label_cols))
        else:
            table.columns[i].width = int(width * day_share)

    for c, val in enumerate(header_row):
        style_cell(table.cell(0, c), val, size=font_size, bold=True, fill=NAVY, font_color=WHITE, align=PP_ALIGN.CENTER)

    for r, row in enumerate(body, start=1):
        for c, (text, fill) in enumerate(row):
            if c < label_cols:
                style_cell(
                    table.cell(r, c),
                    text,
                    size=font_size + 1,
                    bold=(c == 0 and text != ""),
                    fill=WHITE,
                    font_color=NAVY,
                    align=PP_ALIGN.CENTER,
                )
            else:
                bg = fill if fill is not None else WHITE
                style_cell(
                    table.cell(r, c),
                    text,
                    size=max(6, font_size - 1),
                    bold=False,
                    fill=bg,
                    font_color=INK if text else INK,
                    align=PP_ALIGN.CENTER,
                )
    return shape


def legend_row(slide, left, top, items: list[tuple[str, RGBColor]]):
    x = left
    for label, color in items:
        add_rect(slide, x, top, Inches(0.22), Inches(0.16), color)
        add_text(slide, x + Inches(0.28), top - Inches(0.02), Inches(2.4), Inches(0.22), label, 10, False, INK)
        x += Inches(2.7)


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# --------------------- Executivo ---------------------

def pptx_executivo() -> Path:
    from generate_report import PERIOD_END, PERIOD_START, analyze, load_maintenances

    data = analyze(load_maintenances())
    prs = new_prs()
    period = f"{PERIOD_START.strftime('%d/%m')} a {PERIOD_END.strftime('%d/%m/%Y')}"
    bucket_order = ["Cabeamento", "Switch", "Câmera", "Cartão de Memória"]

    slide = blank_slide(prs)
    y = title_bar(slide, "Relatório Executivo CFTV — Manutenções", f"Período {period}")
    cards = [
        ("Período", period),
        ("Manutenções", fmt_int(data.n_maints)),
        ("Reincidências", fmt_int(data.n_reinc)),
        ("Câmeras retirada", fmt_int(data.n_cameras_retirada)),
    ]
    w, gap = Inches(2.95), Inches(0.18)
    for i, (lab, val) in enumerate(cards):
        kpi_card(slide, Inches(0.35) + i * (w + gap), y, w, Inches(0.85), lab, val)
    add_text(slide, Inches(0.35), y + Inches(1.0), Inches(6), Inches(0.3), "Resumo por garagem", 14, True, NAVY)
    rows = [["Garagem", "Manutenções", "Reincidências"]]
    rows += [[g, fmt_int(m), fmt_int(r)] for g, m, r in data.garage_rows]
    add_table(
        slide,
        Inches(0.35),
        y + Inches(1.3),
        Inches(12.6),
        Inches(5.0),
        rows,
        [0.55, 0.225, 0.225],
        font_size=11,
    )

    slide = blank_slide(prs)
    y = title_bar(slide, "Principais problemas e ações", period)
    add_text(slide, Inches(0.35), y, Inches(6), Inches(0.28), "Problemas por Grupo — Veículo", 13, True, NAVY)
    rows = [["Grupo", "Quantidade"]] + [[k, fmt_int(v)] for k, v in data.top_problem_buckets]
    add_table(slide, Inches(0.35), y + Inches(0.3), Inches(5.9), Inches(2.0), rows, [0.65, 0.35], font_size=12)

    add_text(slide, Inches(6.9), y, Inches(6), Inches(0.28), "Ações por Grupo — Veículo", 13, True, NAVY)
    rows = [["Grupo", "Quantidade"]] + [[k, fmt_int(v)] for k, v in data.top_action_buckets]
    add_table(slide, Inches(6.9), y + Inches(0.3), Inches(5.9), Inches(2.0), rows, [0.65, 0.35], font_size=12)

    y2 = y + Inches(2.55)
    add_text(slide, Inches(0.35), y2, Inches(6), Inches(0.28), "Problemas mais identificados — Câmera", 13, True, NAVY)
    rows = [["Problema", "Qtd"]] + [[k, fmt_int(v)] for k, v in data.top_problems[:9]]
    add_table(slide, Inches(0.35), y2 + Inches(0.3), Inches(6.1), Inches(3.6), rows, [0.75, 0.25], font_size=10)

    add_text(slide, Inches(6.9), y2, Inches(6), Inches(0.28), "Ações mais realizadas — Câmera", 13, True, NAVY)
    rows = [["Ação", "Qtd"]] + [[k, fmt_int(v)] for k, v in data.top_actions[:9]]
    add_table(slide, Inches(6.9), y2 + Inches(0.3), Inches(6.1), Inches(3.6), rows, [0.75, 0.25], font_size=10)

    slide = blank_slide(prs)
    y = title_bar(slide, "Principais problemas por garagem", "Prefixos distintos com ≥1 problema do grupo")
    rows = [["Garagem"] + bucket_order + ["Total"]]
    for garagem, tops in data.garage_bucket_problems:
        counts = dict(tops)
        vals = [counts.get(b, 0) for b in bucket_order]
        rows.append([garagem] + [fmt_int(v) for v in vals] + [fmt_int(sum(vals))])
    add_table(slide, Inches(0.3), y, Inches(12.7), Inches(6.2), rows, font_size=11)

    out = OUT / "Relatorio_Executivo_CFTV.pptx"
    prs.save(out)
    print("PPTX", out)
    return out


# --------------------- Conexão ---------------------

def pptx_conexao() -> Path:
    payload = json.loads((DATA / "conexao_cameras_resumo.json").read_text(encoding="utf-8"))
    rows_all = sorted(
        [r for r in payload["rows"] if r.get("total_veiculos", 0) > 0],
        key=lambda r: r["unidade"].casefold(),
    )
    metro = [r for r in rows_all if r.get("metropole")]
    prs = new_prs()

    def build(title: str, subset: list[dict]):
        slide = blank_slide(prs)
        y = title_bar(slide, title, "NxNet todayOnly · Retirada via Jotform")
        table_rows = [[
            "Unidade", "Região", "Veíc. c/ problema", "Câm. offline", "Câm. erro SD", "Câm. 21", "Retirada"
        ]]
        t = [0, 0, 0, 0, 0]
        for r in subset:
            table_rows.append([
                r["unidade"],
                r["regiao"],
                str(r["veiculos_problema"]),
                str(r["camera_100_offline"]),
                str(r["camera_erro_sd"]),
                str(r["camera_21_problema"]),
                str(r.get("camera_retirada", 0)),
            ])
            t[0] += int(r["veiculos_problema"])
            t[1] += int(r["camera_100_offline"])
            t[2] += int(r["camera_erro_sd"])
            t[3] += int(r["camera_21_problema"])
            t[4] += int(r.get("camera_retirada", 0))
        table_rows.append(["TOTAL", "", *map(str, t)])
        add_table(slide, Inches(0.25), y, Inches(12.8), Inches(6.2), table_rows, font_size=10)

    build("Conexão das Câmeras — Todas as unidades", rows_all)
    build("Conexão das Câmeras — Metrópole", metro)

    out = OUT / "Conexao_Cameras_por_Unidade.pptx"
    prs.save(out)
    print("PPTX", out)
    return out


# --------------------- SD Card ---------------------

def pptx_sdcard() -> Path:
    from generate_status_pdfs import analyze_sd, cameras_for_prefix, load_job, parse_day, pick_latest

    data = load_job(pick_latest("metropole_expandir_*.json"))
    prefixos = data["prefixos_alvo"]
    stats = analyze_sd(data, prefixos)
    days_all = stats["days"]
    d0 = parse_day(days_all[0]).strftime("%d/%m/%Y")
    d1 = parse_day(days_all[-1]).strftime("%d/%m/%Y")
    prs = new_prs()

    # Slide 1 — resumo + problemas
    slide = blank_slide(prs)
    y = title_bar(slide, "Análise dos SD Cards — Metropole Expandir", f"{d0} a {d1}")
    cards = [
        ("Período", f"{parse_day(days_all[0]).strftime('%d/%m')} a {d1}"),
        ("Prefixos", str(len(prefixos))),
        ("SD Cards", str(stats["total_cards"])),
        ("Funcionais", f"{stats['n_ok']} ({stats['n_ok']/stats['total_cards']*100:.1f}%)".replace(".", ",")),
        ("Com erro", f"{stats['n_err']} ({stats['n_err']/stats['total_cards']*100:.1f}%)".replace(".", ",")),
        ("Offline", f"{stats['n_off']} ({stats['n_off']/stats['total_cards']*100:.1f}%)".replace(".", ",")),
    ]
    for i, (lab, val) in enumerate(cards):
        kpi_card(slide, Inches(0.3) + i * Inches(2.15), y, Inches(2.05), Inches(0.8), lab, val)

    add_text(slide, Inches(0.3), y + Inches(0.95), Inches(8), Inches(0.28), "SD Cards com problema", 14, True, NAVY)
    rows = [["Prefixo", "Câmera", "Início", "Fim", "Dias funcionais", "Dias com erro"]]
    for p in stats["problems"]:
        rows.append([
            str(p["prefixo"]),
            str(p["camera"]),
            parse_day(p["inicio"]).strftime("%d/%m/%Y") if p["inicio"] else "-",
            parse_day(p["fim"]).strftime("%d/%m/%Y") if p["fim"] else "-",
            f"{p['ok']} ({p['pct_ok']:.1f}%)".replace(".", ","),
            f"{p['erro']} ({p['pct_erro']:.1f}%)".replace(".", ","),
        ])
    add_table(slide, Inches(0.25), y + Inches(1.25), Inches(12.8), Inches(4.9), rows, font_size=11)

    # Evolução por mês — tabelas coloridas editáveis
    by_month: dict[tuple[int, int], list[str]] = {}
    for day in days_all:
        dd = parse_day(day)
        by_month.setdefault((dd.year, dd.month), []).append(day)
    month_names = {
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    day_index = {d: i for i, d in enumerate(days_all)}
    color_map = {"ok": GREEN, "erro": RED, "off": OFF_BG}

    for (year, month), month_days in sorted(by_month.items()):
        slide = blank_slide(prs)
        label = f"{month_names.get(month, str(month))} {year}"
        y = title_bar(
            slide,
            f"Evolução dos SD Cards — {label}",
            f"{parse_day(month_days[0]).strftime('%d/%m')} a {parse_day(month_days[-1]).strftime('%d/%m/%Y')} · {len(month_days)} dias · tabela editável",
        )
        legend_row(
            slide,
            Inches(0.35),
            y,
            [("Funcional", GREEN), ("Erro", RED), ("Offline", OFF_BG)],
        )
        y += Inches(0.28)

        header = ["Prefixo", "Câm"] + [parse_day(d).strftime("%d/%m") for d in month_days]
        body: list[list[tuple[str, RGBColor | None]]] = []
        for pref in prefixos:
            cams = cameras_for_prefix(data, pref) or [21, 22, 23]
            for ci, cam in enumerate(cams):
                full = stats["statuses"].get((pref, cam), ["off"] * len(days_all))
                row: list[tuple[str, RGBColor | None]] = [
                    (str(pref) if ci == 0 else "", None),
                    (str(cam), None),
                ]
                for d in month_days:
                    st = full[day_index[d]]
                    txt = "OFF" if st == "off" else ""
                    row.append((txt, color_map.get(st, OFF_BG)))
                body.append(row)

        add_heatmap_table(
            slide,
            Inches(0.2),
            y,
            Inches(12.9),
            Inches(5.9),
            header,
            body,
            font_size=7,
            label_cols=2,
        )

    out = OUT / "Analise_SDCard_Metropole_Expandir.pptx"
    prs.save(out)
    print("PPTX", out)
    return out


# --------------------- Santa Brígida ---------------------

def pptx_santa() -> Path:
    from generate_status_pdfs import (
        cameras_for_prefix,
        cell_status_ok,
        load_job,
        parse_day,
        pick_latest,
        pref_day_status,
        prefix_start_map,
    )

    data = load_job(pick_latest("santa_brigida_*.json"))
    starts = prefix_start_map(data)
    prefixos = sorted(data["prefixos_alvo"], key=lambda p: (starts.get(p, date.min), str(p)))
    days = sorted(data["dias"].keys())
    d0 = parse_day(days[0]).strftime("%d/%m/%Y")
    d1 = parse_day(days[-1]).strftime("%d/%m/%Y")
    prs = new_prs()

    # Página 1 — evolução por prefixo (uma linha por prefixo)
    slide = blank_slide(prs)
    y = title_bar(slide, "Evolução dos prefixos — CFTV Santa Brígida", f"{d0} a {d1} · tabela editável")
    legend_row(
        slide,
        Inches(0.35),
        y,
        [("Todos online", GREEN), ("1+ offline", RED), ("Fora do período", GRAY)],
    )
    y += Inches(0.28)
    header = ["Prefixo"] + [parse_day(d).strftime("%d/%m") for d in days]
    body = []
    for pref in prefixos:
        row: list[tuple[str, RGBColor | None]] = [(str(pref), None)]
        for day in days:
            st = pref_day_status(data, pref, day, starts)
            if st == "na":
                row.append(("", GRAY))
            elif st == "ok":
                row.append(("", GREEN))
            else:
                row.append(("", RED))
        body.append(row)
    add_heatmap_table(
        slide,
        Inches(0.2),
        y,
        Inches(12.9),
        Inches(5.9),
        header,
        body,
        font_size=7,
        label_cols=1,
    )

    # Página 2 — por câmera
    slide = blank_slide(prs)
    y = title_bar(slide, "Detalhamento por câmera — CFTV Santa Brígida", f"{d0} a {d1} · tabela editável")
    legend_row(
        slide,
        Inches(0.35),
        y,
        [("Todos online", GREEN), ("1+ offline", RED), ("Fora do período", GRAY)],
    )
    y += Inches(0.28)
    header = ["Prefixo", "Câm"] + [parse_day(d).strftime("%d/%m") for d in days]
    body = []
    for pref in prefixos:
        cams = cameras_for_prefix(data, pref) or [21, 22, 23]
        for ci, cam in enumerate(cams):
            row = [(str(pref) if ci == 0 else "", None), (str(cam), None)]
            for day in days:
                entry = (data["dias"][day]["prefixos"].get(pref) or {})
                if entry.get("status") == "fora_periodo" or (
                    starts.get(pref) and parse_day(day) < starts[pref]
                ):
                    row.append(("", GRAY))
                    continue
                raw = (entry.get("cameras") or {}).get(str(cam))
                st = cell_status_ok(raw)
                row.append(("", GREEN if st == "ok" else RED))
            body.append(row)
    add_heatmap_table(
        slide,
        Inches(0.15),
        y,
        Inches(13.0),
        Inches(5.9),
        header,
        body,
        font_size=6,
        label_cols=2,
    )

    out = OUT / "CFTV_Santa_Brigida.pptx"
    prs.save(out)
    print("PPTX", out)
    return out


def main() -> int:
    outs = [pptx_executivo(), pptx_conexao(), pptx_sdcard(), pptx_santa()]
    for o in outs:
        print(f"  {o.name}: {o.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
