#!/usr/bin/env python3
"""Atualiza dados nos PPTX-modelo via ZIP/XML (preserva layout 100%)."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import zipfile
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
_extra_uploads = os.environ.get("REPORT_UPLOADS", "").strip()
UPLOADS = Path(_extra_uploads) if _extra_uploads else ROOT / "uploads"
TPL = ROOT / "data" / "pptx_templates"
OUT = ROOT / "reports" / "pptx"
DATA = ROOT / "data" / "status_cameras"
OUT.mkdir(parents=True, exist_ok=True)

sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"a": A_NS, "c": C_NS, "p": P_NS}

GREEN = "7BC67E"
RED = "E89A9A"
GRAY = "C5CED6"
PCT_GRAY = "7F7F7F"


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fmt_pct(num: float, digits: int = 1) -> str:
    return f"{num:.{digits}f}".replace(".", ",") + "%"


def load_xml(raw: bytes) -> etree._Element:
    return etree.fromstring(raw)


def dump_xml(root: etree._Element) -> bytes:
    # Declaração no estilo Office (aspas duplas + CRLF) — evita “reparo” no PowerPoint
    body = etree.tostring(root, encoding="UTF-8", xml_declaration=False)
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n' + body


def cell_text(tc: etree._Element) -> str:
    return "".join(t.text or "" for t in tc.xpath(".//a:t", namespaces=NS)).strip()


def _set_rpr_srgb(rPr: etree._Element, rgb: str, *, bold: bool | None = None) -> None:
    if bold is not None:
        if bold:
            rPr.set("b", "1")
        elif "b" in rPr.attrib:
            del rPr.attrib["b"]
    # remove fills existentes
    for node in list(rPr):
        if node.tag == f"{{{A_NS}}}solidFill":
            rPr.remove(node)
    solid = etree.Element(f"{{{A_NS}}}solidFill")
    srgb = etree.SubElement(solid, f"{{{A_NS}}}srgbClr")
    srgb.set("val", rgb)
    rPr.insert(0, solid)


def _set_t_text(t_node: etree._Element, text: str) -> None:
    t_node.text = text
    # PowerPoint descarta espaços sem xml:space=preserve
    if text != text.strip() or "  " in text:
        t_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    elif "{http://www.w3.org/XML/1998/namespace}space" in t_node.attrib:
        del t_node.attrib["{http://www.w3.org/XML/1998/namespace}space"]


def _mark_dirty(rPr: etree._Element | None) -> etree._Element:
    if rPr is None:
        rPr = etree.Element(f"{{{A_NS}}}rPr")
    rPr.set("dirty", "1")
    return rPr


def set_cell_text(tc: etree._Element, text: str) -> None:
    """Substitui o texto da célula por um único run (compatível com PowerPoint)."""
    paras = tc.xpath(".//a:p", namespaces=NS)
    if not paras:
        tx = tc.find(f"{{{A_NS}}}txBody")
        if tx is None:
            return
        p = etree.SubElement(tx, f"{{{A_NS}}}p")
        r = etree.SubElement(p, f"{{{A_NS}}}r")
        rPr = etree.SubElement(r, f"{{{A_NS}}}rPr")
        _mark_dirty(rPr)
        t = etree.SubElement(r, f"{{{A_NS}}}t")
        _set_t_text(t, text)
        return
    para = paras[0]
    runs = para.xpath("./a:r", namespaces=NS)
    if not runs:
        r = etree.SubElement(para, f"{{{A_NS}}}r")
        rPr = etree.SubElement(r, f"{{{A_NS}}}rPr")
        _mark_dirty(rPr)
        t = etree.SubElement(r, f"{{{A_NS}}}t")
        _set_t_text(t, text)
    else:
        r0 = runs[0]
        t = r0.find(f"{{{A_NS}}}t")
        if t is None:
            t = etree.SubElement(r0, f"{{{A_NS}}}t")
        _set_t_text(t, text)
        rPr = r0.find(f"{{{A_NS}}}rPr")
        if rPr is None:
            rPr = etree.Element(f"{{{A_NS}}}rPr")
            r0.insert(0, rPr)
        _mark_dirty(rPr)
        for r in runs[1:]:
            para.remove(r)
    for p in paras[1:]:
        for r in p.xpath("./a:r", namespaces=NS):
            p.remove(r)


def clear_cell_text_keep_structure(tc: etree._Element) -> None:
    """Heatmap: remove runs (sem criar <a:t/> vazio) — PowerPoint rejeita run vazio + fill."""
    for p in tc.xpath(".//a:p", namespaces=NS):
        for r in p.xpath("./a:r", namespaces=NS):
            p.remove(r)


def set_cell_count_and_pct(
    tc: etree._Element,
    count: int,
    pct: float,
    *,
    spacer: str = "    ",
    count_rgb: str | None = None,
    template_tc: etree._Element | None = None,
) -> None:
    """Número + porcentagem (#7F7F7F, sem negrito) em runs separados."""
    pct_txt = f"{pct:.0f}%"
    p = tc.xpath(".//a:p", namespaces=NS)
    if not p:
        set_cell_text(tc, f"{count}{spacer}{pct_txt}")
        return
    para = p[0]
    runs = para.xpath("./a:r", namespaces=NS)

    # Células vazias do modelo (só <a:p/>): clona 3 runs de uma célula-template
    if not runs and template_tc is not None:
        src_runs = template_tc.xpath(".//a:p[1]/a:r", namespaces=NS)
        for src in src_runs[:3]:
            para.append(deepcopy(src))
        runs = para.xpath("./a:r", namespaces=NS)

    while len(runs) < 3:
        base = runs[-1] if runs else None
        if base is not None:
            r = deepcopy(base)
            para.append(r)
        else:
            r = etree.SubElement(para, f"{{{A_NS}}}r")
            rPr = etree.SubElement(r, f"{{{A_NS}}}rPr")
            rPr.set("sz", "1400")
            etree.SubElement(r, f"{{{A_NS}}}t").text = ""
        runs = para.xpath("./a:r", namespaces=NS)
    for r in runs[3:]:
        t = r.find(f"{{{A_NS}}}t")
        if t is not None:
            t.text = ""

    def _run_set(r, text, *, rgb=None, bold=None, sz=None):
        t = r.find(f"{{{A_NS}}}t")
        if t is None:
            t = etree.SubElement(r, f"{{{A_NS}}}t")
        _set_t_text(t, text)
        rPr = r.find(f"{{{A_NS}}}rPr")
        if rPr is None:
            rPr = etree.Element(f"{{{A_NS}}}rPr")
            r.insert(0, rPr)
        if sz is not None:
            rPr.set("sz", str(sz))
        if bold is not None:
            if bold:
                rPr.set("b", "1")
            elif "b" in rPr.attrib:
                del rPr.attrib["b"]
        if rgb is not None:
            _set_rpr_srgb(rPr, rgb, bold=None)
        _mark_dirty(rPr)

    _run_set(runs[0], str(count), rgb=count_rgb, bold=True, sz=1400)
    _run_set(runs[1], spacer, bold=False, sz=1200)
    _run_set(runs[2], pct_txt, rgb=PCT_GRAY, bold=False, sz=1100)
    # endParaRPr com bg1 (branco) faz o PowerPoint “sumir” com texto em alguns temas
    for epr in para.xpath("./a:endParaRPr", namespaces=NS):
        for node in list(epr):
            if node.tag == f"{{{A_NS}}}solidFill":
                epr.remove(node)


def set_cell_fill(tc: etree._Element, rgb: str) -> None:
    """Define solidFill na ordem do schema OOXML (depois das bordas ln*)."""
    tcPr = tc.find(f"{{{A_NS}}}tcPr")
    if tcPr is None:
        tcPr = etree.Element(f"{{{A_NS}}}tcPr")
        tc.append(tcPr)
    for tag in ("solidFill", "gradFill", "noFill", "blipFill", "pattFill"):
        for node in tcPr.findall(f"{{{A_NS}}}{tag}"):
            tcPr.remove(node)
    solid = etree.Element(f"{{{A_NS}}}solidFill")
    srgb = etree.SubElement(solid, f"{{{A_NS}}}srgbClr")
    srgb.set("val", rgb)
    # ECMA-376: ln* / cell3D vêm antes do fill — PowerPoint ignora fill fora de ordem
    insert_at = len(list(tcPr))
    for i, child in enumerate(list(tcPr)):
        local = child.tag.split("}")[-1]
        if local.startswith("ln") or local == "cell3D":
            insert_at = i + 1
    tcPr.insert(insert_at, solid)


def iter_table_rows(slide_root: etree._Element):
    for tbl in slide_root.xpath(".//a:tbl", namespaces=NS):
        rows = tbl.xpath("./a:tr", namespaces=NS)
        yield tbl, rows


def replace_kpi_textbox(slide_root: etree._Element, label_prefix: str, value: str) -> bool:
    """Atualiza textbox KPI (parágrafo label + parágrafo valor)."""
    for sp in slide_root.xpath(".//p:sp", namespaces=NS):
        texts = sp.xpath(".//a:t", namespaces=NS)
        full = "".join(t.text or "" for t in texts)
        if not full.startswith(label_prefix) and label_prefix not in full.split("\n")[0]:
            # match início do primeiro texto
            if not texts or not (texts[0].text or "").startswith(label_prefix[:4]):
                continue
        # heurística: se contém o label
        joined = "|".join(t.text or "" for t in texts)
        if label_prefix not in joined and not joined.startswith(label_prefix[:3]):
            continue
        # encontra runs por parágrafo
        paras = sp.xpath(".//a:p", namespaces=NS)
        if len(paras) >= 2:
            t0 = paras[0].xpath(".//a:t", namespaces=NS)
            t1 = paras[1].xpath(".//a:t", namespaces=NS)
            if t0:
                # mantém label do modelo no 1º parágrafo
                pass
            if t1:
                t1[0].text = value
                for t in t1[1:]:
                    t.text = ""
                return True
    return False


def _chart_embed_path(files: dict, chart_xml_name: str) -> str | None:
    """Resolve ppt/embeddings/*.xlsx ligado ao gráfico via .rels."""
    rels_name = chart_xml_name.replace("ppt/charts/", "ppt/charts/_rels/") + ".rels"
    raw = files.get(rels_name)
    if not raw:
        return None
    rels = etree.fromstring(raw)
    for rel in rels:
        target = rel.get("Target") or ""
        if target.endswith(".xlsx"):
            # Target é relativo a ppt/charts/
            return "ppt/embeddings/" + Path(target).name
    return None


def update_embedded_xlsx(files: dict, embed_path: str, categories: list[str], values: list[int], series_name: str = "Série 1") -> None:
    """PowerPoint lê os gráficos do XLSX embutido — precisa atualizar junto com o cache XML."""
    from openpyxl import load_workbook

    raw = files.get(embed_path)
    if not raw:
        print("WARN embed ausente:", embed_path)
        return
    wb = load_workbook(BytesIO(raw))
    ws = wb.active
    ws["A1"] = " "
    ws["B1"] = series_name
    for i, (cat, val) in enumerate(zip(categories, values), start=2):
        ws.cell(i, 1, cat)
        ws.cell(i, 2, int(val))
    buf = BytesIO()
    wb.save(buf)
    files[embed_path] = buf.getvalue()
    print(f"  embed {Path(embed_path).name}: {list(zip(categories, values))}")


def update_chart_doughnut(
    files: dict,
    chart_xml_name: str,
    online: int,
    offline: int,
    title_parts: list[str] | None = None,
) -> None:
    chart_root = load_xml(files[chart_xml_name])
    vals = [str(online), str(offline)]
    for cache in chart_root.xpath(".//c:numCache", namespaces=NS):
        pts = cache.xpath("./c:pt", namespaces=NS)
        for i, pt in enumerate(pts):
            v = pt.find(f"{{{C_NS}}}v")
            if v is not None and i < len(vals):
                v.text = vals[i]
        ptCount = cache.find(f"{{{C_NS}}}ptCount")
        if ptCount is not None:
            ptCount.set("val", str(len(vals)))
    for lit in chart_root.xpath(".//c:numLit", namespaces=NS):
        pts = lit.xpath("./c:pt", namespaces=NS)
        for i, pt in enumerate(pts):
            v = pt.find(f"{{{C_NS}}}v")
            if v is not None and i < len(vals):
                v.text = vals[i]
    cats = ["Online", "Offline"]
    for cache in chart_root.xpath(".//c:strCache", namespaces=NS):
        pts = cache.xpath("./c:pt", namespaces=NS)
        if len(pts) < 2:
            continue
        labels = [(pt.find(f"{{{C_NS}}}v").text or "") for pt in pts]
        if any(x in {"Vendas", "Online", "Offline", "OK", "Falha"} for x in labels):
            for i, cat in enumerate(cats):
                v = pts[i].find(f"{{{C_NS}}}v")
                if v is not None:
                    v.text = cat
    if title_parts:
        titles = chart_root.xpath(".//c:title//a:t", namespaces=NS)
        for i, node in enumerate(titles):
            node.text = title_parts[i] if i < len(title_parts) else ""
        if titles and len(title_parts) > len(titles):
            titles[-1].text = "".join(title_parts[len(titles) - 1 :])
    files[chart_xml_name] = dump_xml(chart_root)
    embed = _chart_embed_path(files, chart_xml_name)
    if embed:
        update_embedded_xlsx(files, embed, cats, [online, offline], series_name="Vendas")


def update_chart_bar(files: dict, chart_xml_name: str, categories: list[str], values: list[int]) -> None:
    chart_root = load_xml(files[chart_xml_name])
    for cache in chart_root.xpath(".//c:strCache", namespaces=NS):
        pts = cache.xpath("./c:pt", namespaces=NS)
        if len(pts) == 1 and (pts[0].find(f"{{{C_NS}}}v").text or "").startswith("Série"):
            continue
        if len(pts) >= len(categories):
            for i, cat in enumerate(categories):
                v = pts[i].find(f"{{{C_NS}}}v")
                if v is not None:
                    v.text = cat
    for cache in chart_root.xpath(".//c:numCache", namespaces=NS):
        pts = cache.xpath("./c:pt", namespaces=NS)
        for i, val in enumerate(values):
            if i < len(pts):
                v = pts[i].find(f"{{{C_NS}}}v")
                if v is not None:
                    v.text = str(val)
    files[chart_xml_name] = dump_xml(chart_root)
    embed = _chart_embed_path(files, chart_xml_name)
    if embed:
        update_embedded_xlsx(files, embed, categories, values, series_name="Série 1")


def patch_pptx(src: Path, dst: Path, mutator) -> None:
    """Regrava o PPTX preservando ordem e compressão originais (crítico p/ PowerPoint)."""
    buf = BytesIO()
    with zipfile.ZipFile(src, "r") as zin:
        order = zin.namelist()
        infos = {i.filename: i for i in zin.infolist()}
        files = {name: zin.read(name) for name in order}
        mutator(files)
        with zipfile.ZipFile(buf, "w") as zout:
            for name in order:
                if name not in files:
                    continue
                info = zipfile.ZipInfo(filename=name)
                info.compress_type = infos[name].compress_type
                info.date_time = infos[name].date_time
                zout.writestr(info, files[name])
            # partes novas (ex.: se mutator criar algo)
            for name, raw in files.items():
                if name not in infos:
                    zout.writestr(name, raw)
    dst.write_bytes(buf.getvalue())


# ---------------- data ----------------

def real_data():
    from generate_report import PERIOD_END, PERIOD_START, analyze, load_maintenances
    from generate_status_pdfs import load_job, parse_day, pick_latest, pref_day_status, prefix_start_map

    report = analyze(load_maintenances())
    santa = load_job(pick_latest("santa_brigida_*.json"))
    conexao = json.loads((DATA / "conexao_cameras_resumo.json").read_text(encoding="utf-8"))
    return report, (PERIOD_START, PERIOD_END), santa, conexao, parse_day, pref_day_status, prefix_start_map


# ---------------- Executivo ----------------

def mutate_executivo(files: dict, report, period):
    d0, d1 = period
    period_lbl = f"{d0.strftime('%d/%m')} a {d1.strftime('%d/%m/%Y')}"

    # slide1 KPIs + tabela
    s1 = load_xml(files["ppt/slides/slide1.xml"])
    # KPI values: procura text boxes pelo conteúdo
    # Período value no 2º parágrafo do textbox que começa com Período
    for sp in s1.xpath(".//p:sp", namespaces=NS):
        texts = sp.xpath(".//a:t", namespaces=NS)
        if not texts:
            continue
        first = texts[0].text or ""
        paras = sp.xpath(".//a:p", namespaces=NS)
        if first.startswith("Período") and len(paras) >= 2:
            ts = paras[1].xpath(".//a:t", namespaces=NS)
            if ts:
                ts[0].text = period_lbl
                for t in ts[1:]:
                    t.text = ""
        elif first.startswith("Manutenções") and len(paras) >= 2:
            ts = paras[1].xpath(".//a:t", namespaces=NS)
            if ts:
                ts[0].text = fmt_int(report.n_maints)
                for t in ts[1:]:
                    t.text = ""
        elif first.startswith("Reincidências") and len(paras) >= 2:
            ts = paras[1].xpath(".//a:t", namespaces=NS)
            if ts:
                ts[0].text = fmt_int(report.n_reinc)
                for t in ts[1:]:
                    t.text = ""
        elif first.startswith("Câmeras") and len(paras) >= 2:
            ts = paras[1].xpath(".//a:t", namespaces=NS)
            if ts:
                ts[0].text = fmt_int(report.n_cameras_retirada)
                for t in ts[1:]:
                    t.text = ""

    garage_map = {g.casefold(): (m, r) for g, m, r in report.garage_rows}
    unmatched = []
    for tbl, rows in iter_table_rows(s1):
        for tr in rows[1:]:
            cells = tr.xpath("./a:tc", namespaces=NS)
            if len(cells) < 4:
                continue
            g = " ".join(cell_text(cells[0]).split())
            match = garage_map.get(g.casefold())
            if not match:
                for k, v in garage_map.items():
                    if k in g.casefold() or g.casefold() in k:
                        match = v
                        break
            if not match:
                unmatched.append(g)
                continue
            m, r = match
            set_cell_text(cells[1], fmt_int(m))
            set_cell_text(cells[2], fmt_int(r))
            set_cell_text(cells[3], fmt_pct((r / m * 100) if m else 0.0, 1))
    if unmatched:
        print("WARN Executivo garagens sem match:", unmatched)
    files["ppt/slides/slide1.xml"] = dump_xml(s1)

    # slide2 tops + chart
    s2 = load_xml(files["ppt/slides/slide2.xml"])
    tables = list(iter_table_rows(s2))
    if len(tables) >= 2:
        for (tbl, rows), items in (
            (tables[0], report.top_problems[:9]),
            (tables[1], report.top_actions[:9]),
        ):
            for i, (label, qty) in enumerate(items):
                ri = i + 2
                if ri >= len(rows):
                    break
                cells = rows[ri].xpath("./a:tc", namespaces=NS)
                if len(cells) < 3:
                    continue
                set_cell_text(cells[0], str(i + 1))
                set_cell_text(cells[1], label)
                set_cell_text(cells[2], fmt_int(qty))
    files["ppt/slides/slide2.xml"] = dump_xml(s2)

    if "ppt/charts/chart1.xml" in files:
        order = ["Cartão de Memória", "Câmera", "Cabeamento", "Switch"]
        buckets = dict(report.top_problem_buckets)
        update_chart_bar(files, "ppt/charts/chart1.xml", order, [buckets.get(k, 0) for k in order])

    # slide3 matrix
    s3 = load_xml(files["ppt/slides/slide3.xml"])
    bucket_order = ["Cabeamento", "Switch", "Câmera", "Cartão de Memória"]
    gmap = {g.casefold(): dict(tops) for g, tops in report.garage_bucket_problems}
    for tbl, rows in iter_table_rows(s3):
        for tr in rows[1:]:
            cells = tr.xpath("./a:tc", namespaces=NS)
            if len(cells) < 6:
                continue
            g = " ".join(cell_text(cells[0]).split())
            counts = gmap.get(g.casefold())
            if not counts:
                for k, v in gmap.items():
                    if k in g.casefold() or g.casefold() in k:
                        counts = v
                        break
            if not counts:
                continue
            vals = [counts.get(b, 0) for b in bucket_order]
            for ci, v in enumerate(vals, start=1):
                set_cell_text(cells[ci], fmt_int(v))
            set_cell_text(cells[5], fmt_int(sum(vals)))
    files["ppt/slides/slide3.xml"] = dump_xml(s3)


# ---------------- Conexão ----------------

def mutate_conexao(files: dict, conexao: dict):
    by = {r["unidade"].casefold(): r for r in conexao["rows"] if r.get("total_veiculos", 0) > 0}

    def fill(slide_name: str):
        root = load_xml(files[slide_name])
        unmatched = []
        for tbl, rows in iter_table_rows(root):
            totals = [0, 0, 0, 0, 0]
            for tr in rows[1:-1]:
                cells = tr.xpath("./a:tc", namespaces=NS)
                if len(cells) < 7:
                    continue
                name = " ".join(cell_text(cells[0]).split())
                r = by.get(name.casefold())
                if not r:
                    for k, v in by.items():
                        if name.casefold() in k or k in name.casefold():
                            r = v
                            break
                if not r:
                    unmatched.append(name)
                    continue
                vals = [
                    str(r["regiao"]),
                    str(r["veiculos_problema"]),
                    str(r["camera_100_offline"]),
                    str(r["camera_erro_sd"]),
                    str(r["camera_21_problema"]),
                    str(r.get("camera_retirada", 0)),
                ]
                for ci, v in enumerate(vals, start=1):
                    set_cell_text(cells[ci], v)
                for i in range(5):
                    totals[i] += int(vals[i + 1])
            # TOTAL
            if len(rows) >= 2:
                cells = rows[-1].xpath("./a:tc", namespaces=NS)
                if len(cells) >= 7:
                    set_cell_text(cells[0], "TOTAL")
                    set_cell_text(cells[1], "")
                    for i, v in enumerate(totals):
                        set_cell_text(cells[i + 2], str(v))
        if unmatched:
            print(f"WARN Conexão ({slide_name}) unidades sem match:", unmatched)
        files[slide_name] = dump_xml(root)

    fill("ppt/slides/slide1.xml")
    fill("ppt/slides/slide2.xml")


# ---------------- Santa ----------------

def _set_avail_label(sp: etree._Element, pct: float) -> None:
    paras = sp.xpath(".//a:p", namespaces=NS)
    if not paras:
        return
    ts = paras[0].xpath(".//a:t", namespaces=NS)
    if ts:
        _set_t_text(ts[0], fmt_pct(pct, 1).replace("%", " %"))
        for t in ts[1:]:
            t.text = ""
    if len(paras) >= 2:
        ts2 = paras[1].xpath(".//a:t", namespaces=NS)
        if ts2:
            ts2[0].text = "Disponibilidade"
            for t in ts2[1:]:
                t.text = ""


def _update_chart_user_shapes(files: dict, pct: float) -> None:
    """Atualiza o rótulo no buraco da pizza (ppt/drawings/*) — PowerPoint lê daqui, não do slide."""
    for name, raw in list(files.items()):
        if not name.startswith("ppt/drawings/") or not name.endswith(".xml"):
            continue
        root = load_xml(raw)
        changed = False
        for sp in root.xpath(".//*[local-name()='sp']"):
            texts = sp.xpath(".//a:t", namespaces=NS)
            full = "".join(x.text or "" for x in texts)
            if "Disponibilidade" not in full and "%" not in full:
                continue
            _set_avail_label(sp, pct)
            changed = True
        if changed:
            files[name] = dump_xml(root)
            print(f"  drawing {name}: disponibilidade -> {fmt_pct(pct, 1)}")


def _resize_heatmap_day_cols(tbl: etree._Element, n_days: int) -> None:
    """Ajusta colunas de dias da tabela de evolução (mantém a 1ª coluna Prefixo)."""
    grid = tbl.find(f"{{{A_NS}}}tblGrid")
    if grid is None:
        return
    cols = grid.xpath("./a:gridCol", namespaces=NS)
    if len(cols) < 2:
        return
    pref_w = int(cols[0].get("w") or 600000)
    day_cols = cols[1:]
    cur = len(day_cols)
    # largura total das colunas de dia permanece a mesma
    total_day_w = sum(int(c.get("w") or 0) for c in day_cols) or (400000 * max(cur, 1))
    proto_col = day_cols[-1]
    rows = tbl.xpath("./a:tr", namespaces=NS)

    if n_days > cur:
        for _ in range(n_days - cur):
            grid.append(deepcopy(proto_col))
            for tr in rows:
                cells = tr.xpath("./a:tc", namespaces=NS)
                tr.append(deepcopy(cells[-1]))
    elif n_days < cur:
        for _ in range(cur - n_days):
            cols = grid.xpath("./a:gridCol", namespaces=NS)
            grid.remove(cols[-1])
            for tr in rows:
                cells = tr.xpath("./a:tc", namespaces=NS)
                tr.remove(cells[-1])

    day_cols = grid.xpath("./a:gridCol", namespaces=NS)[1:]
    if not day_cols:
        return
    each = max(120000, total_day_w // len(day_cols))
    rem = total_day_w - each * len(day_cols)
    for i, c in enumerate(day_cols):
        c.set("w", str(each + (rem if i == len(day_cols) - 1 else 0)))
    # garante largura do prefixo
    grid.xpath("./a:gridCol", namespaces=NS)[0].set("w", str(pref_w))


def _set_santa_heatmap_title(slide_root: etree._Element, subtitle: str) -> None:
    """Atualiza o título do slide de evolução com o mês."""
    for sp in slide_root.xpath(".//p:sp", namespaces=NS):
        texts = sp.xpath(".//a:t", namespaces=NS)
        joined = "".join(t.text or "" for t in texts)
        if "Evolução CFTV" not in joined:
            continue
        # Mantém "Evolução CFTV — Santa Brígida" e acrescenta o período do mês
        if not texts:
            continue
        # reescreve como 2 linhas: título + subtítulo
        paras = sp.xpath(".//a:p", namespaces=NS)
        if not paras:
            continue
        # 1º parágrafo: título base
        runs = paras[0].xpath("./a:r", namespaces=NS)
        if runs:
            t0 = runs[0].find(f"{{{A_NS}}}t")
            if t0 is not None:
                t0.text = "Evolução CFTV — Santa Brígida"
            for r in runs[1:]:
                tt = r.find(f"{{{A_NS}}}t")
                if tt is not None:
                    tt.text = ""
        # 2º parágrafo (ou cria): subtítulo do mês
        if len(paras) >= 2:
            runs2 = paras[1].xpath("./a:r", namespaces=NS)
            if runs2:
                t1 = runs2[0].find(f"{{{A_NS}}}t")
                if t1 is None:
                    t1 = etree.SubElement(runs2[0], f"{{{A_NS}}}t")
                t1.text = subtitle
                for r in runs2[1:]:
                    tt = r.find(f"{{{A_NS}}}t")
                    if tt is not None:
                        tt.text = ""
            else:
                r = etree.SubElement(paras[1], f"{{{A_NS}}}r")
                rPr = etree.SubElement(r, f"{{{A_NS}}}rPr")
                rPr.set("sz", "1400")
                t = etree.SubElement(r, f"{{{A_NS}}}t")
                t.text = subtitle
        else:
            p = etree.SubElement(paras[0].getparent(), f"{{{A_NS}}}p")
            r = etree.SubElement(p, f"{{{A_NS}}}r")
            rPr = etree.SubElement(r, f"{{{A_NS}}}rPr")
            rPr.set("sz", "1400")
            t = etree.SubElement(r, f"{{{A_NS}}}t")
            t.text = subtitle
        break


def _fill_santa_heatmap_slide(
    slide_root: etree._Element,
    *,
    santa,
    starts,
    window: list[str],
    parse_day,
    pref_day_status,
    subtitle: str,
) -> None:
    _set_santa_heatmap_title(slide_root, subtitle)
    color = {"ok": GREEN, "bad": RED, "na": GRAY}
    for tbl, rows in iter_table_rows(slide_root):
        _resize_heatmap_day_cols(tbl, len(window))
        rows = tbl.xpath("./a:tr", namespaces=NS)
        header_cells = rows[0].xpath("./a:tc", namespaces=NS)
        for ci, day in enumerate(window, start=1):
            if ci < len(header_cells):
                set_cell_text(header_cells[ci], parse_day(day).strftime("%d/%m"))
        # limpa cabeçalhos sobrando (se houver)
        for ci in range(len(window) + 1, len(header_cells)):
            clear_cell_text_keep_structure(header_cells[ci])
        for tr in rows[1:]:
            cells = tr.xpath("./a:tc", namespaces=NS)
            pref = cell_text(cells[0])
            for ci, day in enumerate(window, start=1):
                if ci >= len(cells):
                    break
                st = pref_day_status(santa, pref, day, starts)
                set_cell_fill(cells[ci], color.get(st, GRAY))
                clear_cell_text_keep_structure(cells[ci])


def _ensure_santa_month_slides(files: dict, n_months: int) -> list[str]:
    """Garante slide2..slideN de evolução (clona slide2). Retorna paths dos slides mensais."""
    if n_months < 1:
        return []
    base = "ppt/slides/slide2.xml"
    base_rels = "ppt/slides/_rels/slide2.xml.rels"
    slide_paths = [base]
    # clona bytes do slide2 para slide3..
    for i in range(3, n_months + 2):
        path = f"ppt/slides/slide{i}.xml"
        rels = f"ppt/slides/_rels/slide{i}.xml.rels"
        files[path] = files[base]
        # rels sem notes (evita conflito de notesSlide compartilhado)
        rels_root = etree.fromstring(files[base_rels])
        for rel in list(rels_root):
            typ = rel.get("Type") or ""
            if typ.endswith("/notesSlide"):
                rels_root.remove(rel)
        files[rels] = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
            + etree.tostring(rels_root, encoding="UTF-8", xml_declaration=False)
        )
        slide_paths.append(path)

    # Content_Types
    ct = load_xml(files["[Content_Types].xml"])
    ns_ct = {"ct": "http://schemas.openxmlformats.org/package/2006/content-types"}
    existing = {
        (n.get("PartName") or "")
        for n in ct.xpath("//ct:Override", namespaces=ns_ct)
    }
    for path in slide_paths:
        part = "/" + path
        if part in existing:
            continue
        ov = etree.SubElement(ct, "{http://schemas.openxmlformats.org/package/2006/content-types}Override")
        ov.set("PartName", part)
        ov.set(
            "ContentType",
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )
    files["[Content_Types].xml"] = dump_xml(ct)

    # presentation.xml.rels — rIds para slides extras
    rels = load_xml(files["ppt/_rels/presentation.xml.rels"])
    rel_ns = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
    used_ids = {r.get("Id") for r in rels}
    slide_rid = {}
    for path in slide_paths:
        target = path.replace("ppt/", "")
        found = None
        for r in rels:
            if (r.get("Target") or "").replace("\\", "/") == target:
                found = r.get("Id")
                break
        if found:
            slide_rid[path] = found
            continue
        n = 9
        while f"rId{n}" in used_ids:
            n += 1
        rid = f"rId{n}"
        used_ids.add(rid)
        rel = etree.SubElement(
            rels,
            "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship",
        )
        rel.set("Id", rid)
        rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
        )
        rel.set("Target", target)
        slide_rid[path] = rid
    files["ppt/_rels/presentation.xml.rels"] = dump_xml(rels)

    # presentation.xml sldIdLst na ordem: slide1 + slides mensais
    pres = load_xml(files["ppt/presentation.xml"])
    sld_lst = pres.find(f"{{{P_NS}}}sldIdLst")
    if sld_lst is None:
        return slide_paths
    # preserva slide1 (primeiro); reconstrói o restante
    first = list(sld_lst)[0] if list(sld_lst) else None
    for child in list(sld_lst):
        sld_lst.remove(child)
    if first is not None:
        sld_lst.append(first)
    next_id = 262
    for path in slide_paths:
        sld = etree.SubElement(sld_lst, f"{{{P_NS}}}sldId")
        sld.set("id", str(next_id))
        sld.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", slide_rid[path])
        next_id += 1
    files["ppt/presentation.xml"] = dump_xml(pres)
    return slide_paths


def mutate_santa(files: dict, santa, parse_day, pref_day_status, prefix_start_map):
    starts = prefix_start_map(santa)
    prefixos = sorted(santa["prefixos_alvo"], key=lambda p: (starts.get(p, date.min), str(p)))
    # ignora dias sem câmeras (ex.: 17/11 ainda ausente no historico)
    from generate_status_pdfs import _day_has_cameras

    days = sorted(d for d, bucket in santa["dias"].items() if _day_has_cameras(bucket))

    # Total = dias com dado extraído (ok+bad), sem fora do período
    stats = {}
    for pref in prefixos:
        ok = bad = 0
        for day in days:
            st = pref_day_status(santa, pref, day, starts)
            if st == "ok":
                ok += 1
            elif st == "bad":
                bad += 1
        stats[pref] = (ok, bad, ok + bad)

    months_present = sorted({parse_day(d).month for d in days})
    month_names = {
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    month_counts = {}
    for month in months_present:
        ok = bad = 0
        month_days = [d for d in days if parse_day(d).month == month]
        for day in month_days:
            for pref in prefixos:
                st = pref_day_status(santa, pref, day, starts)
                if st == "ok":
                    ok += 1
                elif st == "bad":
                    bad += 1
        month_counts[month] = (ok, bad, month_days)

    s1 = load_xml(files["ppt/slides/slide1.xml"])

    # % disponibilidade: slide (1º mês) + chart drawing (2º mês — userShapes do chart2)
    first_month = months_present[0] if months_present else 9
    second_month = months_present[1] if len(months_present) > 1 else first_month
    m1_ok, m1_bad, m1_days = month_counts.get(first_month, (0, 0, []))
    m2_ok, m2_bad, m2_days = month_counts.get(second_month, (0, 0, []))
    m1_pct = (m1_ok / (m1_ok + m1_bad) * 100) if (m1_ok + m1_bad) else 0.0
    m2_pct = (m2_ok / (m2_ok + m2_bad) * 100) if (m2_ok + m2_bad) else 0.0

    # remove clones antigos que sobrepunham o drawing do chart2
    tree = s1.find(f".//{{{P_NS}}}spTree")
    if tree is not None:
        for sp in list(s1.xpath(".//p:sp", namespaces=NS)):
            nv = sp.find(f".//{{{P_NS}}}cNvPr")
            if nv is not None and nv.get("name") == "Disponibilidade Outubro":
                tree.remove(sp)

    for sp in s1.xpath(".//p:sp", namespaces=NS):
        full = "".join(t.text or "" for t in sp.xpath(".//a:t", namespaces=NS))
        if "Disponibilidade" in full:
            _set_avail_label(sp, m1_pct)
            break
    _update_chart_user_shapes(files, m2_pct)

    for tbl, rows in iter_table_rows(s1):
        # 1ª linha de dados com runs OK/falha serve de template para células vazias
        template_ok = template_bad = None
        for tr in rows[1:]:
            cells = tr.xpath("./a:tc", namespaces=NS)
            if len(cells) >= 4 and cells[2].xpath(".//a:r", namespaces=NS):
                template_ok = cells[2]
            if len(cells) >= 4 and cells[3].xpath(".//a:r", namespaces=NS):
                template_bad = cells[3]
            if template_ok is not None and template_bad is not None:
                break
        unmatched = []
        for tr in rows[1:]:
            cells = tr.xpath("./a:tc", namespaces=NS)
            if len(cells) < 4:
                continue
            pref = cell_text(cells[0])
            if pref not in stats:
                unmatched.append(pref)
                continue
            ok, bad, tot = stats[pref]
            set_cell_text(cells[1], str(tot))
            ok_pct = (ok / tot * 100) if tot else 0.0
            bad_pct = (bad / tot * 100) if tot else 0.0
            set_cell_count_and_pct(cells[2], ok, ok_pct, spacer="    ", template_tc=template_ok)
            set_cell_count_and_pct(
                cells[3],
                bad,
                bad_pct,
                spacer="  ",
                count_rgb="FF0000",
                template_tc=template_bad if template_bad is not None else template_ok,
            )
        if unmatched:
            print("WARN Santa prefixos sem match na tabela:", unmatched)
    files["ppt/slides/slide1.xml"] = dump_xml(s1)

    if "ppt/charts/chart1.xml" in files:
        title = (
            [
                month_names.get(first_month, str(first_month)),
                f" ({parse_day(m1_days[0]).strftime('%d/%m')} a {parse_day(m1_days[-1]).strftime('%d/%m')})",
            ]
            if m1_days
            else [month_names.get(first_month, str(first_month)), ""]
        )
        update_chart_doughnut(files, "ppt/charts/chart1.xml", m1_ok, m1_bad, title)
    if "ppt/charts/chart2.xml" in files:
        title = (
            [
                month_names.get(second_month, str(second_month)),
                f" ({parse_day(m2_days[0]).strftime('%d/%m')} a {parse_day(m2_days[-1]).strftime('%d/%m')})",
            ]
            if m2_days
            else [month_names.get(second_month, str(second_month)), ""]
        )
        update_chart_doughnut(files, "ppt/charts/chart2.xml", m2_ok, m2_bad, title)

    # Um slide de heatmap por mês (28/09…16/11 → set/out/nov)
    slide_paths = _ensure_santa_month_slides(files, len(months_present))
    for month, slide_path in zip(months_present, slide_paths):
        _ok, _bad, month_days = month_counts[month]
        subtitle = (
            f"{month_names.get(month, str(month))} "
            f"({parse_day(month_days[0]).strftime('%d/%m')} a {parse_day(month_days[-1]).strftime('%d/%m/%Y')})"
            if month_days
            else month_names.get(month, str(month))
        )
        root = load_xml(files[slide_path])
        _fill_santa_heatmap_slide(
            root,
            santa=santa,
            starts=starts,
            window=month_days,
            parse_day=parse_day,
            pref_day_status=pref_day_status,
            subtitle=subtitle,
        )
        files[slide_path] = dump_xml(root)
        print(f"  Santa heatmap {slide_path}: {subtitle} · {len(month_days)} dias")


# ---------------- SD Card ----------------

def mutate_sdcard(files: dict, metro, parse_day, analyze_sd, cameras_for_prefix, cell_status_sd):
    prefixos = metro["prefixos_alvo"]
    stats = analyze_sd(metro, prefixos)
    days = stats["days"]
    d0 = parse_day(days[0]).strftime("%d/%m/%Y")
    d1 = parse_day(days[-1]).strftime("%d/%m/%Y")
    period_lbl = f"{parse_day(days[0]).strftime('%d/%m')} a {parse_day(days[-1]).strftime('%d/%m/%Y')}"
    total = stats["total_cards"] or 1

    s1 = load_xml(files["ppt/slides/slide1.xml"])
    for sp in s1.xpath(".//p:sp", namespaces=NS):
        texts = sp.xpath(".//a:t", namespaces=NS)
        if not texts:
            continue
        first = texts[0].text or ""
        paras = sp.xpath(".//a:p", namespaces=NS)
        if len(paras) < 2:
            continue
        val_ts = paras[1].xpath(".//a:t", namespaces=NS)
        if not val_ts:
            continue
        if first.startswith("Período"):
            val_ts[0].text = period_lbl
        elif first.startswith("Prefixos"):
            val_ts[0].text = str(len(prefixos))
        elif first.lower().startswith("sdcard") or first.startswith("SDCards") or first.startswith("SD Cards"):
            val_ts[0].text = str(stats["total_cards"])
        elif first.startswith("Funcionais"):
            val_ts[0].text = f"{stats['n_ok']} ({stats['n_ok']/total*100:.1f}%)".replace(".", ",")
        elif "Falha" in first or first.startswith("Com"):
            val_ts[0].text = f"{stats['n_err']} ({stats['n_err']/total*100:.1f}%)".replace(".", ",")
        for t in val_ts[1:]:
            t.text = ""

    # tabela problemas — inclui número da câmera
    problems = stats["problems"]
    for tbl, rows in iter_table_rows(s1):
        # header: Prefixo | Câmera | Início | Fim | Dias funcionais | Dias com erro
        for i, p in enumerate(problems):
            ri = i + 1
            if ri >= len(rows):
                break
            cells = rows[ri].xpath("./a:tc", namespaces=NS)
            if len(cells) < 6:
                continue
            set_cell_text(cells[0], str(p["prefixo"]))
            set_cell_text(cells[1], str(p["camera"]))  # número da câmera (21/22/23…)
            set_cell_text(cells[2], parse_day(p["inicio"]).strftime("%d/%m/%Y") if p["inicio"] else "-")
            set_cell_text(cells[3], parse_day(p["fim"]).strftime("%d/%m/%Y") if p["fim"] else "-")
            set_cell_text(cells[4], f"{p['ok']} ({p['pct_ok']:.1f}%)".replace(".", ","))
            set_cell_text(cells[5], f"{p['erro']} ({p['pct_erro']:.1f}%)".replace(".", ","))
        # limpa linhas sobrando
        for ri in range(len(problems) + 1, len(rows)):
            cells = rows[ri].xpath("./a:tc", namespaces=NS)
            for c in cells:
                set_cell_text(c, "")
    files["ppt/slides/slide1.xml"] = dump_xml(s1)

    # slide2 — evolução por câmera (barrinha fina por slot 21/22/23)
    s2 = load_xml(files["ppt/slides/slide2.xml"])
    for tbl, rows in iter_table_rows(s2):
        header = rows[0]
        header_cells = header.xpath("./a:tc", namespaces=NS)
        n_day_cols = len(header_cells) - 1
        window = days[-n_day_cols:] if len(days) >= n_day_cols else days
        for ci, day in enumerate(window, start=1):
            if ci < len(header_cells):
                set_cell_text(header_cells[ci], parse_day(day).strftime("%d/%m"))

        # Linhas do modelo = 1 por prefixo; expandimos para 1 por câmera.
        template_rows = rows[1:]
        prefix_order = [cell_text(tr.xpath("./a:tc", namespaces=NS)[0]) for tr in template_rows]
        if not prefix_order:
            continue

        # Remove linhas de dados atuais; reinsere clones finos por câmera.
        for tr in template_rows:
            tbl.remove(tr)

        table_h = sum(int(r.get("h") or 0) for r in rows) or 5410020
        header_h = int(header.get("h") or 300000)
        # monta lista (prefixo, câmera)
        cam_rows: list[tuple[str, int]] = []
        for pref in prefix_order:
            cams = cameras_for_prefix(metro, pref) or [21, 22, 23]
            for cam in cams:
                cam_rows.append((pref, cam))
        n_data = max(len(cam_rows), 1)
        data_h = max(90000, (table_h - header_h) // n_data)
        # ajusta header se sobrar/faltou 1 EMU de arredondamento
        header.set("h", str(header_h))

        proto = template_rows[0]
        for pref, cam in cam_rows:
            tr = deepcopy(proto)
            tr.set("h", str(data_h))
            cells = tr.xpath("./a:tc", namespaces=NS)
            # Prefixo/câmera na 1ª coluna (ex.: 32704/21)
            set_cell_text(cells[0], f"{pref}/{cam}")
            # fonte menor na label para caber na barrinha
            for t in cells[0].xpath(".//a:rPr", namespaces=NS):
                t.set("sz", "700")
            for ci, day in enumerate(window, start=1):
                if ci >= len(cells):
                    break
                raw = (
                    ((metro["dias"].get(day) or {}).get("prefixos") or {}).get(pref) or {}
                ).get("cameras") or {}
                st = cell_status_sd(raw.get(str(cam)))
                if st == "erro":
                    fill = RED
                elif st == "off":
                    fill = GRAY
                else:
                    fill = GREEN
                set_cell_fill(cells[ci], fill)
                clear_cell_text_keep_structure(cells[ci])
            tbl.append(tr)
    files["ppt/slides/slide2.xml"] = dump_xml(s2)


def libreoffice_resave(path: Path) -> None:
    """Regrava o PPTX via LibreOffice."""
    import subprocess

    tmp = path.parent / "_lo_resave"
    tmp.mkdir(parents=True, exist_ok=True)
    for old in tmp.glob("*.pptx"):
        old.unlink()
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pptx", "--outdir", str(tmp), str(path)],
        check=True,
        capture_output=True,
    )
    converted = tmp / path.name
    if not converted.exists():
        cands = list(tmp.glob("*.pptx"))
        if not cands:
            raise FileNotFoundError(f"LibreOffice não gerou {path.name}")
        converted = cands[0]
    shutil.move(str(converted), str(path))
    print("  LO-resave", path.name, path.stat().st_size)


def finalize_for_powerpoint(path: Path) -> None:
    """
    Normaliza o pacote para o Microsoft PowerPoint:
    1) python-pptx regrava texto das tabelas (estrutura que o Office aceita)
    2) mantém fills/gráficos já patchados no XML
    """
    from pptx import Presentation

    prs = Presentation(str(path))
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_table:
                continue
            table = shape.table
            # Só reescreve células que já têm texto (não mexe no heatmap colorido)
            for row in table.rows:
                for cell in row.cells:
                    txt = cell.text
                    if txt.strip():
                        cell.text = txt
    prs.save(str(path))
    print("  pptx-normalize", path.name, path.stat().st_size)


def main() -> int:
    pristine = ROOT / "data" / "pptx_templates_pristine"
    models = {
        "exec": TPL / "Relatorio_Executivo_CFTV.pptx",
        "santa": TPL / "CFTV_Santa_Brigida.pptx",
        "conexao": TPL / "Conexao_Cameras_por_Unidade.pptx",
        "sdcard": TPL / "Analise_SDCard_Metropole_Expandir.pptx",
    }
    upload_map = {
        "exec": UPLOADS / "Relatorio_Executivo_CFTV_4aea.pptx",
        "santa": UPLOADS / "CFTV_Santa_Brigida_7fd3.pptx",
        "conexao": UPLOADS / "Conexao_Cameras_por_Unidade_cb07.pptx",
        "sdcard": UPLOADS / "Analise_SDCard_Metropole_Expandir_8818.pptx",
    }
    TPL.mkdir(parents=True, exist_ok=True)
    pristine.mkdir(parents=True, exist_ok=True)

    # Fonte do layout: uploads → pristine (uma vez) → templates de trabalho
    for k, dest in models.items():
        src = upload_map[k] if upload_map[k].exists() else None
        prist = pristine / dest.name
        if src is not None and (not prist.exists() or src.stat().st_mtime > prist.stat().st_mtime):
            shutil.copy2(src, prist)
        if prist.exists():
            shutil.copy2(prist, dest)
        elif src is not None:
            shutil.copy2(src, dest)

    for p in models.values():
        if not p.exists():
            print("Modelo ausente:", p, file=sys.stderr)
            return 2

    from generate_status_pdfs import analyze_sd, cameras_for_prefix, cell_status_sd, load_job, pick_latest

    report, period, santa, conexao, parse_day, pref_day_status, prefix_start_map = real_data()
    metro = load_job(pick_latest("metropole_expandir_*.json"))
    print("Periodo executivo:", period[0], period[1], "manuts", report.n_maints)
    print("Santa dias:", sorted(santa["dias"])[0], "->", sorted(santa["dias"])[-1])
    print("Metro dias:", sorted(metro["dias"])[0], "->", sorted(metro["dias"])[-1])
    print("Conexao veiculos:", sum(int(r["veiculos_problema"]) for r in conexao["rows"]))

    from datetime import datetime
    from zoneinfo import ZoneInfo

    stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d_%H%M")
    outs = {
        "exec": OUT / "Relatorio_Executivo_CFTV.pptx",
        "santa": OUT / "CFTV_Santa_Brigida.pptx",
        "conexao": OUT / "Conexao_Cameras_por_Unidade.pptx",
        "sdcard": OUT / "Analise_SDCard_Metropole_Expandir.pptx",
    }
    dated = {k: OUT / f"{outs[k].stem}_{stamp}.pptx" for k in outs}

    patch_pptx(models["exec"], outs["exec"], lambda f: mutate_executivo(f, report, period))
    patch_pptx(models["santa"], outs["santa"], lambda f: mutate_santa(f, santa, parse_day, pref_day_status, prefix_start_map))
    patch_pptx(models["conexao"], outs["conexao"], lambda f: mutate_conexao(f, conexao))
    patch_pptx(
        models["sdcard"],
        outs["sdcard"],
        lambda f: mutate_sdcard(f, metro, parse_day, analyze_sd, cameras_for_prefix, cell_status_sd),
    )

    for k in outs:
        # Normaliza texto de tabelas simples via python-pptx (Office-safe).
        # Santa mantém runs OK/% coloridos do patch XML — não achatar.
        if k in {"exec", "conexao", "sdcard"}:
            try:
                finalize_for_powerpoint(outs[k])
            except Exception as exc:
                print("WARN pptx-normalize falhou:", outs[k].name, exc)
        shutil.copy2(outs[k], dated[k])
        # também atualiza o nome sem horário (evita download antigo)
        plain_dated = OUT / f"{outs[k].stem}_{date.today().isoformat()}.pptx"
        shutil.copy2(outs[k], plain_dated)
        print("OK", outs[k], outs[k].stat().st_size)
        print("OK", dated[k])
    print("STAMP", stamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
