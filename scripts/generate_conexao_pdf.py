#!/usr/bin/env python3
"""PDF 2 páginas: conexão das câmeras — duas tabelas lado a lado."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "status_cameras" / "conexao_cameras_resumo.json"
OUT = ROOT / "reports" / "Conexao_Cameras_por_Unidade.pdf"

def register_fonts():
    from font_paths import liberation_pair

    regular, bold = liberation_pair()
    pdfmetrics.registerFont(TTFont("Arial", regular))
    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))

NAVY = "#1F3340"
CARD = "#F5F7F9"
MUTED = "#5C6B73"
INK = "#1F2933"


def page_bg(c, width, height):
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=1, stroke=0)


def draw_simple_table(
    c,
    x: float,
    y: float,
    title: str,
    headers: list[str],
    col_w: list[float],
    rows: list[list[str]],
    total_row: list[str],
    row_h: float,
    header_h: float = 26,
) -> float:
    table_w = sum(col_w)
    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 10)
    c.drawString(x, y + 6, title)

    c.setFillColor(HexColor(NAVY))
    c.rect(x, y - header_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 7.5)
    cx = x
    for w, h in zip(col_w, headers):
        if " " in h and len(h) > 12:
            a, b = h.split(" ", 1)
            c.drawCentredString(cx + w / 2, y - 11, a)
            c.drawCentredString(cx + w / 2, y - 21, b)
        else:
            c.drawCentredString(cx + w / 2, y - 16, h)
        cx += w
    y -= header_h

    for i, vals in enumerate(rows):
        bg = white if i % 2 == 0 else HexColor(CARD)
        c.setFillColor(bg)
        c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#E6EBEE"))
        c.setLineWidth(0.4)
        c.line(x, y - row_h, x + table_w, y - row_h)
        c.setFillColor(HexColor(INK))
        cx = x
        text_y = y - row_h / 2 - 3
        for j, (w, v) in enumerate(zip(col_w, vals)):
            if j == 0:
                name = v if len(v) <= 26 else v[:23] + "…"
                c.setFont("Arial", 7.5)
                c.drawString(cx + 5, text_y, name)
            else:
                c.setFont("Arial", 8)
                c.drawCentredString(cx + w / 2, text_y, v)
            cx += w
        y -= row_h

    c.setFillColor(HexColor(NAVY))
    c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 8)
    cx = x
    text_y = y - row_h / 2 - 3
    for j, (w, v) in enumerate(zip(col_w, total_row)):
        if j == 0:
            c.drawString(cx + 5, text_y, v)
        else:
            c.drawCentredString(cx + w / 2, text_y, v)
        cx += w
    y -= row_h

    c.setStrokeColor(HexColor("#C9D2D8"))
    c.setLineWidth(0.8)
    c.rect(x, y, table_w, header_h + (len(rows) + 1) * row_h, fill=0, stroke=1)
    return y


def draw_page(c, width, height, title: str, rows: list[dict], page: int, total: int = 2):
    page_bg(c, width, height)
    margin = 14
    c.setFillColor(HexColor(NAVY))
    c.rect(0, height - 38, width, 38, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 14)
    c.drawString(margin, height - 24, title)

    y = height - 58
    n = len(rows) + 1
    avail = y - 48
    row_h = min(20.0, max(13.5, avail / max(n, 1)))

    gap = 12
    left_w = (width - 2 * margin - gap) * 0.62
    right_w = (width - 2 * margin - gap) * 0.38
    left_x = margin
    right_x = margin + left_w + gap

    # Tabela 1 — situação geral (offline inclui câmera 21)
    h1 = ["Unidade", "Região", "Veículos c/ problema", "Câmeras offline", "Câm. erro SD"]
    c1 = [
        left_w * 0.38,
        left_w * 0.12,
        left_w * 0.20,
        left_w * 0.16,
        left_w * 0.14,
    ]
    rows1 = []
    t_veic = t_off = t_sd = t_cam21 = t_ret = t_cams = 0
    for r in rows:
        rows1.append(
            [
                r["unidade"],
                r["regiao"],
                str(r["veiculos_problema"]),
                str(r["camera_100_offline"]),
                str(r["camera_erro_sd"]),
            ]
        )
        t_veic += int(r["veiculos_problema"])
        t_off += int(r["camera_100_offline"])
        t_sd += int(r["camera_erro_sd"])
        t_cam21 += int(r["camera_21_problema"])
        t_ret += int(r.get("camera_retirada", 0))
        t_cams += int(r.get("cameras_problema", 0))

    # Tabela 2 — câmera 21 e retirada
    h2 = ["Unidade", "Câmera 21", "Câmera retirada"]
    c2 = [right_w * 0.50, right_w * 0.25, right_w * 0.25]
    rows2 = [
        [r["unidade"], str(r["camera_21_problema"]), str(r.get("camera_retirada", 0))]
        for r in rows
    ]

    draw_simple_table(
        c,
        left_x,
        y,
        "Situação geral",
        h1,
        c1,
        rows1,
        ["TOTAL", "", str(t_veic), str(t_off), str(t_sd)],
        row_h,
    )
    draw_simple_table(
        c,
        right_x,
        y,
        "Câmera 21 e retirada",
        h2,
        c2,
        rows2,
        ["TOTAL", str(t_cam21), str(t_ret)],
        row_h,
    )

    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 9)
    summary = (
        f"Veículos com problema: {t_veic:,}   ·   "
        f"Câmeras com problema: {t_cams:,}"
    ).replace(",", ".")
    c.drawString(margin, 28, summary)
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 7)
    c.drawString(
        margin,
        14,
        "Fonte: nxnetv3 · todayOnly · Câmeras offline incluem a câmera 21 · Retirada via Jotform",
    )
    c.drawRightString(width - margin, 14, f"{page} / {total}")


def main():
    register_fonts()
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    rows = sorted(payload["rows"], key=lambda r: r["unidade"].casefold())
    rows = [r for r in rows if r.get("total_veiculos", 0) > 0]
    metro = [r for r in rows if r.get("metropole")]

    width, height = landscape(A4)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=landscape(A4))
    c.setTitle("Conexão das Câmeras por Unidade")
    draw_page(c, width, height, "Conexão das Câmeras — Todas as unidades", rows, 1)
    c.showPage()
    draw_page(c, width, height, "Conexão das Câmeras — Metrópole", metro, 2)
    c.save()
    print("PDF", OUT)


if __name__ == "__main__":
    main()
