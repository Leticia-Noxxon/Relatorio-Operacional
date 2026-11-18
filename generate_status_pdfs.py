#!/usr/bin/env python3
"""Gera PDFs atualizados: SD Cards Metropole Expandir + CFTV Santa Brígida."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "status_cameras"
OUT = ROOT / "reports"
OUT.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

NAVY = "#1F3340"
GREEN = "#7BC67E"
RED = "#E89A9A"
OFF_BG = "#D9DEE3"
CARD = "#F3F5F7"
MUTED = "#5C6B73"
INK = "#1F2933"


def register_fonts():
    pdfmetrics.registerFont(TTFont("Arial", FONT_REG))
    pdfmetrics.registerFont(TTFont("Arial-Bold", FONT_BOLD))


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def _day_has_cameras(day_bucket: dict) -> bool:
    for p in (day_bucket.get("prefixos") or {}).values():
        if p.get("cameras"):
            return True
        if p.get("status") in ("ok", "coletado"):
            return True
    return False


def load_job(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    # remove dias finais sem nenhum prefixo (ex.: dia corrente ainda sem consolidação)
    days = sorted(data.get("dias") or {})
    while days:
        last = days[-1]
        if _day_has_cameras(data["dias"][last]):
            break
        del data["dias"][last]
        days.pop()
    if days:
        data.setdefault("periodo", {})["fim"] = days[-1]
    data["prefixos_alvo"] = [str(p) for p in data.get("prefixos_alvo") or []]
    return data


def parse_day(s: str) -> date:
    return date.fromisoformat(s)


def cell_status_ok(cam: dict | None) -> str:
    """Santa Brígida: verde = todos online; vermelho = 1+ offline."""
    if not cam:
        return "bad"
    if int(cam.get("dias_offline") or 0) > 0:
        return "bad"
    return "ok"


def cell_status_sd(cam: dict | None) -> str:
    if not cam:
        return "off"
    if int(cam.get("dias_offline") or 0) > 0:
        return "off"
    if int(cam.get("dias_sem_dado") or 0) > 0 and int(cam.get("dias_ok") or 0) == 0 and int(cam.get("dias_sd_erro") or 0) == 0:
        return "off"
    if int(cam.get("dias_sd_erro") or 0) > 0:
        return "erro"
    return "ok"


def page_bg(c, width, height) -> None:
    """Fundo branco explícito (evita preview preto em tema escuro)."""
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=1, stroke=0)


def header(c, width, height, title: str, subtitle: str | None = None) -> float:
    page_bg(c, width, height)
    bar_h = 42 if subtitle else 36
    c.setFillColor(HexColor(NAVY))
    c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 16)
    c.drawString(20, height - (22 if not subtitle else 18), title)
    if subtitle:
        c.setFont("Arial", 9)
        c.drawString(20, height - 34, subtitle)
        return height - 56
    return height - 50


def footer(c, width, text: str, page: int, total: int):
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 8)
    c.drawString(28, 14, text)
    c.drawRightString(width - 28, 14, f"{page} / {total}")


def draw_legend(c, x, y, items):
    c.setFont("Arial", 9)
    for label, color, kind in items:
        c.setFillColor(HexColor(color))
        c.roundRect(x, y - 2, 16, 11, 2, fill=1, stroke=0)
        if kind == "off":
            c.setFillColor(HexColor(MUTED))
            c.setFont("Arial", 6)
            c.drawCentredString(x + 8, y + 1, "OFF")
            c.setFont("Arial", 9)
        c.setFillColor(HexColor(INK))
        c.drawString(x + 22, y, label)
        x += max(120, 28 + len(label) * 5.2)


def build_matrix(data: dict, prefixos: list[str], cameras: list[int], mode: str):
    days = sorted(data["dias"].keys())
    matrix = {}  # (pref, cam, day) -> status
    for day in days:
        bucket = data["dias"][day]["prefixos"]
        for pref in prefixos:
            entry = bucket.get(pref) or {}
            cams = entry.get("cameras") or {}
            for cam in cameras:
                raw = cams.get(str(cam))
                matrix[(pref, cam, day)] = cell_status_sd(raw) if mode == "sd" else cell_status_ok(raw)
    return days, matrix


def cameras_for_prefix(data: dict, pref: str) -> list[int]:
    found = set()
    for day in data["dias"].values():
        cams = ((day.get("prefixos") or {}).get(pref) or {}).get("cameras") or {}
        for k in cams:
            found.add(int(k))
    return sorted(found) if found else [21, 22, 23]


# --------------------- Metropole SD ---------------------

def analyze_sd(data: dict, prefixos: list[str]):
    days = sorted(data["dias"].keys())
    n_days = len(days)
    statuses = {}  # (pref,cam) -> list status per day
    for pref in prefixos:
        cams = cameras_for_prefix(data, pref) or [21, 22, 23]
        for cam in cams:
            seq = []
            for day in days:
                raw = (((data["dias"][day]["prefixos"].get(pref) or {}).get("cameras") or {}).get(str(cam)))
                seq.append(cell_status_sd(raw))
            statuses[(pref, cam)] = seq

    total_cards = len(statuses)
    # classificação final do cartão no período
    final = {}
    for key, seq in statuses.items():
        if all(s == "off" for s in seq):
            final[key] = "off"
        elif any(s == "erro" for s in seq):
            final[key] = "erro"
        else:
            final[key] = "ok"

    n_ok = sum(1 for v in final.values() if v == "ok")
    n_err = sum(1 for v in final.values() if v == "erro")
    n_off = sum(1 for v in final.values() if v == "off")

    # dias com pelo menos um erro de SD
    days_with_err = 0
    for i, day in enumerate(days):
        if any(seq[i] == "erro" for seq in statuses.values()):
            days_with_err += 1

    # tabela problemas
    problems = []
    for (pref, cam), seq in statuses.items():
        if final[(pref, cam)] != "erro":
            continue
        err_idx = [i for i, s in enumerate(seq) if s == "erro"]
        ok_days = sum(1 for s in seq if s == "ok")
        err_days = len(err_idx)
        start = days[err_idx[0]] if err_idx else None
        # fim contínuo no final?
        end = None
        if err_idx:
            # último bloco contínuo
            end_i = err_idx[-1]
            # se erro até o último dia, fim aberto
            if end_i == len(days) - 1:
                end = None
            else:
                end = days[end_i]
        problems.append(
            {
                "prefixo": pref,
                "camera": cam,
                "inicio": start,
                "fim": end,
                "ok": ok_days,
                "erro": err_days,
                "pct_ok": ok_days / n_days * 100 if n_days else 0,
                "pct_erro": err_days / n_days * 100 if n_days else 0,
            }
        )
    problems.sort(key=lambda x: (-x["erro"], x["prefixo"], x["camera"]))

    # registros approx: cameras * days * ~24? original had hourly - we don't have; use cameras*days*24 as estimate from online
    # Better: leave as sum of known - use n_days * total non-absent camera-days * 24 rough
    registros = 0
    for day in days:
        for pref in prefixos:
            cams = (data["dias"][day]["prefixos"].get(pref) or {}).get("cameras") or {}
            registros += len(cams) * 24

    return {
        "days": days,
        "n_days": n_days,
        "statuses": statuses,
        "final": final,
        "n_ok": n_ok,
        "n_err": n_err,
        "n_off": n_off,
        "total_cards": total_cards,
        "days_with_err": days_with_err,
        "problems": problems,
        "registros": registros,
        "prefixos": prefixos,
    }


def pdf_metropole(data: dict, out_path: Path):
    register_fonts()
    prefixos = data["prefixos_alvo"]
    stats = analyze_sd(data, prefixos)
    days = stats["days"]
    d0 = parse_day(days[0]).strftime("%d/%m/%Y")
    d1 = parse_day(days[-1]).strftime("%d/%m/%Y")
    width, height = landscape(A4)
    margin = 16
    c = canvas.Canvas(str(out_path), pagesize=landscape(A4))
    c.setTitle(f"Análise dos SD Cards — Metropole Expandir — {d0} a {d1}")

    # page 1 — 6 cards (tudo em 1 linha) + tabela
    y = header(c, width, height, "Análise dos SD Cards — Metropole Expandir")
    d0s = parse_day(days[0]).strftime("%d/%m")
    d1s = parse_day(days[-1]).strftime("%d/%m/%Y")
    cards = [
        ("Período analisado", f"{d0s} a {d1s}", None),
        ("Prefixos analisados", str(len(prefixos)), None),
        ("Total de SD Cards", str(stats["total_cards"]), None),
        (
            "SD Cards funcionais",
            f"{stats['n_ok']} ({stats['n_ok']/stats['total_cards']*100:.1f}%)".replace(".", ","),
            GREEN,
        ),
        (
            "SD Cards com erro",
            f"{stats['n_err']} ({stats['n_err']/stats['total_cards']*100:.1f}%)".replace(".", ","),
            RED,
        ),
        (
            "SD Cards offline",
            f"{stats['n_off']} ({stats['n_off']/stats['total_cards']*100:.1f}%)".replace(".", ","),
            OFF_BG,
        ),
    ]
    gap = 10
    card_w = (width - 2 * margin - 5 * gap) / 6
    card_h = 52
    for i, (lab, val, accent) in enumerate(cards):
        x = margin + i * (card_w + gap)
        c.setFillColor(HexColor(CARD))
        c.roundRect(x, y - card_h, card_w, card_h, 5, fill=1, stroke=0)
        if accent:
            c.setFillColor(HexColor(accent))
            c.rect(x, y - card_h, 5, card_h, fill=1, stroke=0)
        c.setFillColor(HexColor(MUTED))
        c.setFont("Arial-Bold", 9)
        c.drawString(x + 12, y - 16, lab)
        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial-Bold", 12 if len(val) < 18 else 10)
        c.drawString(x + 12, y - 38, val)

    y = y - card_h - 16
    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 12)
    c.drawString(margin, y, "SD Cards com problema")
    y -= 10

    headers = ["Prefixo", "Câmera", "Data de início", "Data de fim", "Dias funcionais", "Dias com erro"]
    table_w = width - 2 * margin
    col_w = [table_w * 0.14, table_w * 0.12, table_w * 0.18, table_w * 0.18, table_w * 0.19, table_w * 0.19]
    problems = stats["problems"]
    avail_h = y - 34
    header_h = 24
    n_rows = max(len(problems), 1)
    # tabela um pouco menor (não estica demais)
    row_h = min(26.0, max(18.0, (avail_h - header_h) / n_rows))

    c.setFillColor(HexColor(NAVY))
    c.roundRect(margin, y - header_h, table_w, header_h, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 11)
    cx = margin
    for idx, (w, h) in enumerate(zip(col_w, headers)):
        if idx <= 1:
            c.drawCentredString(cx + w / 2, y - 18, h)
        else:
            c.drawString(cx + 14, y - 18, h)
        cx += w
    y -= header_h

    for i, p in enumerate(problems):
        bg = white if i % 2 == 0 else HexColor(CARD)
        c.setFillColor(bg)
        c.rect(margin, y - row_h, table_w, row_h, fill=1, stroke=0)
        # separadores verticais leves para marcar a largura útil
        c.setStrokeColor(HexColor("#E4E9ED"))
        c.setLineWidth(0.6)
        cx = margin
        for w in col_w[:-1]:
            cx += w
            c.line(cx, y, cx, y - row_h)
        c.setFillColor(HexColor(INK))
        vals = [
            str(p["prefixo"]),
            str(p["camera"]),
            parse_day(p["inicio"]).strftime("%d/%m/%Y") if p["inicio"] else "-",
            parse_day(p["fim"]).strftime("%d/%m/%Y") if p["fim"] else "-",
            f"{p['ok']} ({p['pct_ok']:.1f}%)".replace(".", ","),
            f"{p['erro']} ({p['pct_erro']:.1f}%)".replace(".", ","),
        ]
        cx = margin
        text_y = y - row_h / 2 - 4
        c.setFont("Arial", 12)
        for idx, (w, v) in enumerate(zip(col_w, vals)):
            if idx <= 1:
                c.drawCentredString(cx + w / 2, text_y, v)
            else:
                c.drawString(cx + 14, text_y, v)
            cx += w
        y -= row_h

    # Evolução: uma página por mês (setembro, outubro, …)
    month_pages: list[tuple[str, list[str]]] = []
    by_month: dict[tuple[int, int], list[str]] = {}
    for day in days:
        dd = parse_day(day)
        by_month.setdefault((dd.year, dd.month), []).append(day)
    month_names = {
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
    for (year, month), month_days in sorted(by_month.items()):
        label = f"{month_names.get(month, str(month))} {year}"
        month_pages.append((label, month_days))

    total_pages = 1 + len(month_pages)
    footer(c, width, f"Metropole Expandir · SD Cards · {d0} a {d1}", 1, total_pages)
    c.showPage()

    for page_i, (month_label, month_days) in enumerate(month_pages, start=2):
        draw_sd_evolution_page(
            c,
            data=data,
            stats=stats,
            prefixos=prefixos,
            days=month_days,
            title=f"Evolução dos SD Cards — {month_label}",
            period_footer=f"Metropole Expandir · SD Cards · {d0} a {d1}",
            page=page_i,
            total_pages=total_pages,
        )
        if page_i < total_pages:
            c.showPage()

    c.save()
    print("PDF", out_path)


def draw_sd_evolution_page(
    c,
    *,
    data: dict,
    stats: dict,
    prefixos: list[str],
    days: list[str],
    title: str,
    period_footer: str,
    page: int,
    total_pages: int,
):
    """Grade de evolução dos SD Cards para um subconjunto de dias (ex.: um mês)."""
    width, height = landscape(A4)
    margin = 16
    all_days = stats["days"]
    day_index = {d: i for i, d in enumerate(all_days)}

    y = header(c, width, height, title)
    d0m = parse_day(days[0]).strftime("%d/%m")
    d1m = parse_day(days[-1]).strftime("%d/%m/%Y")
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 10)
    c.drawString(
        margin,
        y,
        f"{d0m} a {d1m}  ·  {len(days)} dias  ·  {stats['total_cards']} SD Cards",
    )
    y -= 14
    draw_legend(
        c,
        margin,
        y,
        [("Funcional", GREEN, "ok"), ("Erro", RED, "bad"), ("Offline", OFF_BG, "off")],
    )
    y -= 12

    left = margin
    right = width - margin
    pref_w, cam_w = 58, 36
    n = len(days)
    total_rows = 0
    pref_cams = []
    for pref in prefixos:
        cams = cameras_for_prefix(data, pref) or [21, 22, 23]
        pref_cams.append((pref, cams))
        total_rows += len(cams)

    date_header_h = 28
    bottom = 32
    avail_w = right - left - pref_w - cam_w
    avail_h = y - bottom - date_header_h
    cell_w = avail_w / max(n, 1)
    block_gap = 3
    gaps_total = block_gap * max(len(pref_cams) - 1, 0)
    row_h = (avail_h - gaps_total) / max(total_rows, 1)

    c.setFont("Arial-Bold", 8)
    c.setFillColor(HexColor(NAVY))
    c.drawString(left, y - 2, "Prefixo")
    c.drawString(left + pref_w, y - 2, "Câm")
    for i, day in enumerate(days):
        dd = parse_day(day)
        c.saveState()
        c.translate(left + pref_w + cam_w + i * cell_w + cell_w * 0.35, y - 4)
        c.rotate(55)
        c.setFont("Arial-Bold", 8)
        c.setFillColor(HexColor(NAVY))
        c.drawString(0, 0, dd.strftime("%d/%m"))
        c.restoreState()
    y -= date_header_h

    for pi, (pref, cams) in enumerate(pref_cams):
        for ci, cam in enumerate(cams):
            full_seq = stats["statuses"].get((pref, cam), ["off"] * len(all_days))
            seq = [full_seq[day_index[d]] for d in days]
            if ci == 0:
                c.setFillColor(HexColor(NAVY))
                c.setFont("Arial-Bold", 9)
                c.drawString(left, y - row_h / 2 - 3, str(pref))
            c.setFillColor(HexColor(INK))
            c.setFont("Arial", 9)
            c.drawRightString(left + pref_w + cam_w - 4, y - row_h / 2 - 3, str(cam))
            cell_pad_x = 0.4
            cell_pad_y = max(0.8, row_h * 0.08)
            for i, st in enumerate(seq):
                x = left + pref_w + cam_w + i * cell_w
                bx = x + cell_pad_x
                by = y - row_h + cell_pad_y
                bw = cell_w - 2 * cell_pad_x
                bh = row_h - 2 * cell_pad_y
                if st == "ok":
                    c.setFillColor(HexColor(GREEN))
                    c.rect(bx, by, bw, bh, fill=1, stroke=0)
                elif st == "erro":
                    c.setFillColor(HexColor(RED))
                    c.rect(bx, by, bw, bh, fill=1, stroke=0)
                else:
                    c.setFillColor(HexColor(OFF_BG))
                    c.rect(bx, by, bw, bh, fill=1, stroke=0)
                    if cell_w >= 13 and row_h >= 12:
                        c.setFillColor(HexColor(MUTED))
                        c.setFont("Arial", 5)
                        c.drawCentredString(x + cell_w / 2, y - row_h / 2 - 2, "OFF")
            y -= row_h
        if pi < len(pref_cams) - 1:
            y -= block_gap

    footer(c, width, period_footer, page, total_pages)


# --------------------- Santa Brígida ---------------------

GRAY = "#C5CED6"


def prefix_start_map(data: dict) -> dict[str, date]:
    raw = data.get("prefixo_inicio") or {}
    out = {}
    for pref, s in raw.items():
        try:
            out[str(pref)] = parse_day(s)
        except Exception:
            pass
    return out


def pref_day_status(data: dict, pref: str, day: str, starts: dict[str, date]) -> str:
    entry = (data["dias"][day]["prefixos"].get(pref) or {})
    if entry.get("status") == "fora_periodo":
        return "na"
    start = starts.get(pref)
    if start and parse_day(day) < start:
        return "na"
    cams = entry.get("cameras") or {}
    if not cams:
        return "bad"
    offline = any(int(cam.get("dias_offline") or 0) > 0 for cam in cams.values())
    return "bad" if offline else "ok"


LOGO_PATH = ROOT / "data" / "assets" / "noxxon_logo.png"
PCT_GRAY = "#7F7F7F"
HDR_TOTAL = "#B8D4E8"
HDR_OK = "#B7DDB5"
HDR_BAD = "#E8B4B4"


def _santa_header(c, width, height, title: str = "Evolução CFTV — Santa Brígida") -> float:
    """Cabeçalho no layout do modelo PPTX (faixa navy + logo)."""
    page_bg(c, width, height)
    bar_h = 48
    c.setFillColor(HexColor(NAVY))
    c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 18)
    c.drawString(22, height - 31, title)
    if LOGO_PATH.exists():
        # logo branco do modelo (fundo navy)
        logo_h = 30
        logo_w = logo_h * (2362 / 848)
        c.drawImage(
            str(LOGO_PATH),
            width - logo_w - 18,
            height - bar_h + (bar_h - logo_h) / 2,
            width=logo_w,
            height=logo_h,
            mask="auto",
            preserveAspectRatio=True,
        )
    return height - bar_h - 18


def _draw_doughnut(c, cx, cy, r_outer, r_inner, online: int, offline: int):
    total = online + offline
    if total <= 0:
        c.setFillColor(HexColor(GRAY))
        c.circle(cx, cy, r_outer, fill=1, stroke=0)
        c.setFillColor(white)
        c.circle(cx, cy, r_inner, fill=1, stroke=0)
        return
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, Circle
    from reportlab.graphics import renderPDF

    d = Drawing(r_outer * 2, r_outer * 2)
    pie = Pie()
    pie.x = 0
    pie.y = 0
    pie.width = r_outer * 2
    pie.height = r_outer * 2
    pie.data = [online, offline]
    pie.labels = None
    pie.slices.strokeWidth = 0
    pie.slices[0].fillColor = HexColor(GREEN)
    pie.slices[1].fillColor = HexColor(RED)
    pie.startAngle = 90
    pie.direction = "clockwise"
    d.add(pie)
    hole = Circle(r_outer, r_outer, r_inner)
    hole.fillColor = white
    hole.strokeColor = None
    d.add(hole)
    renderPDF.draw(d, c, cx - r_outer, cy - r_outer)


def pdf_santa(data: dict, out_path: Path):
    """PDF no layout do modelo PowerPoint, com dados reais NxNet."""
    register_fonts()
    starts = prefix_start_map(data)
    prefixos = sorted(
        data["prefixos_alvo"],
        key=lambda p: (starts.get(p, date.min), str(p)),
    )
    days = sorted(d for d, bucket in data["dias"].items() if _day_has_cameras(bucket))
    d0 = parse_day(days[0]).strftime("%d/%m/%Y")
    d1 = parse_day(days[-1]).strftime("%d/%m/%Y")
    width, height = landscape(A4)
    c = canvas.Canvas(str(out_path), pagesize=landscape(A4))
    c.setTitle(f"CFTV Santa Brígida — {d0} a {d1}")

    # ---- estatísticas reais ----
    stats = {}
    for pref in prefixos:
        ok = bad = 0
        for day in days:
            st = pref_day_status(data, pref, day, starts)
            if st == "ok":
                ok += 1
            elif st == "bad":
                bad += 1
        stats[pref] = (ok, bad, ok + bad)

    month_counts = {}
    months_present = sorted({parse_day(d).month for d in days})
    for month in months_present:
        ok = bad = 0
        month_days = [d for d in days if parse_day(d).month == month]
        for day in month_days:
            for pref in prefixos:
                st = pref_day_status(data, pref, day, starts)
                if st == "ok":
                    ok += 1
                elif st == "bad":
                    bad += 1
        month_counts[month] = (ok, bad, month_days)

    # ========== PÁGINA 1: tabela + pizzas (layout do modelo) ==========
    y_top = _santa_header(c, width, height)
    margin = 22
    table_right = width * 0.58
    chart_left = table_right + 18

    # tabela
    headers = ["Prefixo", "Total de Registros", "Registros OK", "Registros com falha"]
    hdr_colors = [NAVY, HDR_TOTAL, HDR_OK, HDR_BAD]
    col_w = [78, 130, 130, 150]
    table_w = sum(col_w)
    x0 = margin
    header_h = 28
    n_rows = len(prefixos)
    avail_h = y_top - 36
    row_h = min(36.0, max(26.0, (avail_h - header_h) / max(n_rows, 1)))

    # header row
    x = x0
    for i, (h, w, bg) in enumerate(zip(headers, col_w, hdr_colors)):
        c.setFillColor(HexColor(bg))
        c.rect(x, y_top - header_h, w, header_h, fill=1, stroke=0)
        c.setFillColor(white if i == 0 else HexColor(NAVY))
        c.setFont("Arial-Bold", 9)
        c.drawCentredString(x + w / 2, y_top - 18, h)
        x += w
    y = y_top - header_h

    for ri, pref in enumerate(prefixos):
        ok, bad, tot = stats[pref]
        ok_pct = (ok / tot * 100) if tot else 0.0
        bad_pct = (bad / tot * 100) if tot else 0.0
        bg = white if ri % 2 == 0 else HexColor(CARD)
        c.setFillColor(bg)
        c.rect(x0, y - row_h, table_w, row_h, fill=1, stroke=0)
        # separadores leves
        c.setStrokeColor(HexColor("#E4E9ED"))
        c.setLineWidth(0.5)
        cx = x0
        for w in col_w[:-1]:
            cx += w
            c.line(cx, y, cx, y - row_h)

        ty = y - row_h / 2 - 4
        # Prefixo
        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial-Bold", 11)
        c.drawCentredString(x0 + col_w[0] / 2, ty, str(pref))
        # Total
        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial", 12)
        c.drawCentredString(x0 + col_w[0] + col_w[1] / 2, ty, str(tot))
        # OK count + pct cinza
        ok_x = x0 + col_w[0] + col_w[1] + col_w[2] / 2
        c.setFillColor(HexColor("#2E7D32"))
        c.setFont("Arial-Bold", 12)
        ok_txt = str(ok)
        pct_txt = f"{ok_pct:.0f}%"
        ok_w = c.stringWidth(ok_txt, "Arial-Bold", 12)
        c.setFont("Arial", 10)
        pct_w = c.stringWidth(pct_txt, "Arial", 10)
        gap = 8
        start = ok_x - (ok_w + gap + pct_w) / 2
        c.setFont("Arial-Bold", 12)
        c.setFillColor(HexColor("#2E7D32"))
        c.drawString(start, ty, ok_txt)
        c.setFont("Arial", 10)
        c.setFillColor(HexColor(PCT_GRAY))
        c.drawString(start + ok_w + gap, ty, pct_txt)
        # Falha count vermelho + pct cinza
        bad_x = x0 + col_w[0] + col_w[1] + col_w[2] + col_w[3] / 2
        bad_txt = str(bad)
        bad_pct_txt = f"{bad_pct:.0f}%"
        c.setFont("Arial-Bold", 12)
        bw = c.stringWidth(bad_txt, "Arial-Bold", 12)
        c.setFont("Arial", 10)
        pw = c.stringWidth(bad_pct_txt, "Arial", 10)
        start = bad_x - (bw + gap + pw) / 2
        c.setFont("Arial-Bold", 12)
        c.setFillColor(HexColor("#C62828"))
        c.drawString(start, ty, bad_txt)
        c.setFont("Arial", 10)
        c.setFillColor(HexColor(PCT_GRAY))
        c.drawString(start + bw + gap, ty, bad_pct_txt)
        y -= row_h

    # pizzas mensais (setembro / outubro / novembro …)
    month_names = {
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
    chart_area_w = width - chart_left - margin
    n_months = max(len(months_present), 1)
    # 2 meses: r≈68; 3 meses: encolhe para caber na coluna
    r_outer = 68 if n_months <= 2 else 52
    r_inner = 42 if n_months <= 2 else 32
    cx = chart_left + chart_area_w / 2

    def draw_month_block(top_y: float, title: str, online: int, offline: int, pct: float):
        # título
        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial-Bold", 11 if n_months > 2 else 12)
        c.drawCentredString(cx, top_y, title)
        # legenda
        ly = top_y - 16
        c.setFillColor(HexColor(GREEN))
        c.rect(cx - 70, ly - 2, 12, 12, fill=1, stroke=0)
        c.setFillColor(HexColor(INK))
        c.setFont("Arial", 9)
        c.drawString(cx - 54, ly, "Online")
        c.setFillColor(HexColor(RED))
        c.rect(cx + 10, ly - 2, 12, 12, fill=1, stroke=0)
        c.setFillColor(HexColor(INK))
        c.drawString(cx + 26, ly, "Offline")
        # doughnut
        cy = ly - 14 - r_outer
        _draw_doughnut(c, cx, cy, r_outer, r_inner, online, offline)
        # centro
        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial-Bold", 14 if n_months > 2 else 16)
        pct_lbl = f"{pct:.1f} %".replace(".", ",")
        c.drawCentredString(cx, cy + 4, pct_lbl)
        c.setFont("Arial", 8 if n_months > 2 else 9)
        c.setFillColor(HexColor(MUTED))
        c.drawCentredString(cx, cy - 12, "Disponibilidade")
        return cy - r_outer - (18 if n_months > 2 else 28)

    next_y = y_top - 4
    for month in months_present:
        mok, mbad, mdays = month_counts[month]
        mpct = (mok / (mok + mbad) * 100) if (mok + mbad) else 0.0
        mtitle = (
            f"{month_names.get(month, str(month))} "
            f"({parse_day(mdays[0]).strftime('%d/%m')} a {parse_day(mdays[-1]).strftime('%d/%m')})"
            if mdays
            else month_names.get(month, str(month))
        )
        next_y = draw_month_block(next_y, mtitle, mok, mbad, mpct)

    month_names_full = {
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    month_pages = [
        (m, [d for d in days if parse_day(d).month == m]) for m in months_present
    ]
    month_pages = [(m, md) for m, md in month_pages if md]
    total_pages = 1 + len(month_pages)
    footer(c, width, f"CFTV Santa Brígida · dados reais NxNet · {d0} a {d1}", 1, total_pages)
    c.showPage()

    # ========== Heatmaps: um slide por mês ==========
    for page_i, (month, window) in enumerate(month_pages, start=2):
        y_top = _santa_header(
            c,
            width,
            height,
            title=f"Evolução CFTV — Santa Brígida · {month_names_full.get(month, str(month))}",
        )
        margin = 16
        left = margin
        pref_w = 70
        right = width - margin
        cell_w = (right - left - pref_w) / max(len(window), 1)
        header_h = 34
        legend_h = 28
        bottom = 36
        row_h = (y_top - header_h - legend_h - bottom) / max(len(prefixos), 1)

        c.setFillColor(HexColor(MUTED))
        c.setFont("Arial", 10)
        c.drawString(
            margin,
            y_top + 2,
            f"{parse_day(window[0]).strftime('%d/%m')} a {parse_day(window[-1]).strftime('%d/%m/%Y')}  ·  {len(window)} dias",
        )

        c.setFillColor(HexColor(NAVY))
        c.setFont("Arial-Bold", 10)
        c.drawString(left + 8, y_top - 20, "Prefixo")
        for i, day in enumerate(window):
            c.saveState()
            c.translate(left + pref_w + i * cell_w + cell_w * 0.45, y_top - 8)
            c.rotate(90)
            c.setFont("Arial-Bold", 8)
            c.setFillColor(HexColor(NAVY))
            c.drawString(0, 0, parse_day(day).strftime("%d/%m"))
            c.restoreState()
        y = y_top - header_h

        color = {"ok": GREEN, "bad": RED, "na": GRAY}
        for pref in prefixos:
            c.setFillColor(HexColor(NAVY))
            c.setFont("Arial-Bold", 11)
            c.drawCentredString(left + pref_w / 2, y - row_h / 2 - 4, str(pref))
            for i, day in enumerate(window):
                st = pref_day_status(data, pref, day, starts)
                c.setFillColor(HexColor(color.get(st, GRAY)))
                pad = 0.8
                c.rect(
                    left + pref_w + i * cell_w + pad,
                    y - row_h + pad,
                    cell_w - 2 * pad,
                    row_h - 2 * pad,
                    fill=1,
                    stroke=0,
                )
            c.setStrokeColor(HexColor("#FFFFFF"))
            c.setLineWidth(0.6)
            c.line(left + pref_w, y - row_h, right, y - row_h)
            y -= row_h

        leg_y = 22
        items = [
            (GREEN, "Todas as câmeras Online"),
            (RED, "1 ou + câmera offline"),
            (GRAY, "Fora do período de analise"),
        ]
        lx = margin + 8
        for col, label in items:
            c.setFillColor(HexColor(col))
            c.roundRect(lx, leg_y - 2, 16, 12, 2, fill=1, stroke=0)
            c.setFillColor(HexColor(INK))
            c.setFont("Arial", 9)
            c.drawString(lx + 22, leg_y, label)
            lx += 28 + c.stringWidth(label, "Arial", 9) + 28

        footer(
            c,
            width,
            f"CFTV Santa Brígida · dados reais NxNet · {d0} a {d1}",
            page_i,
            total_pages,
        )
        if page_i < total_pages:
            c.showPage()

    c.save()
    print("PDF", out_path)


def pick_latest(pattern: str) -> Path:
    files = [p for p in DATA.glob(pattern) if p.is_file()]
    if not files:
        raise FileNotFoundError(pattern)

    def score(p: Path) -> tuple:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            days = payload.get("dias") or {}
            with_data = sum(1 for d in days.values() if _day_has_cameras(d))
            return (with_data, len(days), p.stat().st_mtime)
        except Exception:
            return (0, 0, p.stat().st_mtime)

    return max(files, key=score)


def main():
    metro = pick_latest("metropole_expandir_*.json")
    santa = pick_latest("santa_brigida_*.json")
    print("Usando", metro.name, santa.name)
    pdf_metropole(load_job(metro), OUT / "Analise_SDCard_Metropole_Expandir.pdf")
    pdf_santa(load_job(santa), OUT / "CFTV_Santa_Brigida.pdf")


if __name__ == "__main__":
    main()
