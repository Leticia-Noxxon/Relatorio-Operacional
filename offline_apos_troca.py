#!/usr/bin/env python3
"""Cruza trocas de switch com o primeiro OFFLINE posterior nos relatórios diários.

Uma linha de relatório entra como OFFLINE quando qualquer célula contém a
palavra OFFLINE (também off-line). Célula vazia ou só "-" não conta.
O prazo é o primeiro dia de relatório estritamente posterior à data da troca.
"""

from __future__ import annotations

import json
import re
import statistics
import unicodedata
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path("/workspace")
FILES_JSON = Path("/tmp/relatorio_files.json")
SWAPS_TSV = Path("/tmp/troca_switch_tabela.tsv")
DOWNLOAD_DIR = Path("/tmp/relatorios")
OUT_XLSX = ROOT / "data" / "relatorios" / "offline_apos_troca_switch.xlsx"
OUT_TSV = ROOT / "data" / "relatorios" / "offline_apos_troca_switch.tsv"
OUT_PNG = Path("/opt/cursor/artifacts/dias_ate_offline.png")
ART_XLSX = Path("/opt/cursor/artifacts/offline_apos_troca_switch.xlsx")
SUMMARY_JSON = Path("/tmp/offline_apos_troca_resumo.json")

OFFLINE_RE = re.compile(r"off[\s\-]*line", re.IGNORECASE)
DATE_IN_NAME = re.compile(r"(\d{2})[.\-](\d{2})[.\-](\d{2,4})")
RANGE_NAME = re.compile(r"\d{2}[.\-]\d{2}\s*a\s*\d{2}[.\-]\d{2}", re.IGNORECASE)
EMPTY_CELL = {"", "-", "—", "–", "none", "n/a", "na"}

BUCKETS = [
    ("0 a 7 dias", 0, 7),
    ("8 a 15 dias", 8, 15),
    ("16 a 30 dias", 16, 30),
    ("31 a 60 dias", 31, 60),
    ("61 dias ou mais", 61, 10_000),
]


def fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold().strip()


def filename_date(name: str) -> date | None:
    """Data única no nome do arquivo. Intervalos (13-02 a 27-02) não têm data única."""
    if RANGE_NAME.search(name):
        return None
    match = DATE_IN_NAME.search(name)
    if not match:
        return None
    day, month, year_txt = int(match.group(1)), int(match.group(2)), match.group(3)
    if year_txt == "206":
        year = 2026
    elif len(year_txt) == 2:
        year = 2000 + int(year_txt)
    else:
        year = int(year_txt)
    # Arquivos de março nomeados 12.03.2025 são o relatório de 12/03/2026.
    if year == 2025 and "12.03.2025" in name:
        year = 2026
    try:
        return date(year, month, day)
    except ValueError:
        return None


def as_date(value) -> date | None:
    if isinstance(value, datetime):
        found = value.date()
    elif isinstance(value, date):
        found = value
    elif isinstance(value, str):
        text = value.strip()
        found = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                found = datetime.strptime(text[:10], fmt).date()
                break
            except ValueError:
                continue
        if found is None:
            return None
    else:
        return None
    if found.year == 206:
        found = found.replace(year=2026)
    if found.year < 2024 or found.year > 2027:
        return None
    return found


def norm_prefix(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        if value != value:
            return None
        if value == int(value):
            value = int(value)
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = text.replace(" ", "")
    if re.fullmatch(r"\d+", text):
        return text
    return None


def row_has_offline(values) -> bool:
    chunks = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if fold(text) in EMPTY_CELL:
            continue
        chunks.append(text)
    if not chunks:
        return False
    return OFFLINE_RE.search("\n".join(chunks)) is not None


def download(file_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()
    if payload[:2] != b"PK":
        raise RuntimeError(f"resposta nao e xlsx ({payload[:40]!r})")
    dest.write_bytes(payload)


def ensure_downloads(files: list[dict]) -> list[dict]:
    pending = []
    for item in files:
        dest = DOWNLOAD_DIR / f"{item['id']}.xlsx"
        item["path"] = str(dest)
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        pending.append(item)
    if not pending:
        return []
    failures = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(download, item["id"], Path(item["path"])): item for item in pending
        }
        done = 0
        for future in as_completed(futures):
            item = futures[future]
            done += 1
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": item["id"], "name": item["name"], "error": str(exc)})
            if done % 40 == 0 or done == len(pending):
                print(f"download {done}/{len(pending)} falhas {len(failures)}", flush=True)
    return failures


def parse_workbook(item: dict) -> dict:
    path = Path(item["path"])
    fallback = filename_date(item["name"])
    known_2025_typo = "12.03.2025" in item["name"]
    result = {
        "name": item["name"],
        "folder": item["folder"],
        "rows": 0,
        "offline_rows": 0,
        "headers": [],
        "error": None,
        "used_filename_date": False,
        "events": [],  # (prefix, day, offline)
    }
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        return result

    try:
        for sheet in workbook.worksheets:
            if fold(sheet.title).startswith("tabela"):
                continue
            header_row = None
            prefix_col = None
            date_col = None
            for index, row in enumerate(sheet.iter_rows(max_row=25, values_only=True), start=1):
                folded = [fold(str(cell)) if cell is not None else "" for cell in row]
                if any(cell == "prefixo" or cell.startswith("prefixo ") for cell in folded):
                    header_row = index
                    for col, cell in enumerate(folded):
                        if prefix_col is None and (cell == "prefixo" or cell.startswith("prefixo ")):
                            prefix_col = col
                        if date_col is None and cell == "data":
                            date_col = col
                    result["headers"].append(
                        {
                            "sheet": sheet.title,
                            "row": index,
                            "cols": [str(cell) if cell is not None else "" for cell in row if cell],
                        }
                    )
                    break
            if header_row is None or prefix_col is None:
                continue
            for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
                if prefix_col >= len(row):
                    continue
                prefix = norm_prefix(row[prefix_col])
                if prefix is None:
                    continue
                day = None
                if date_col is not None and date_col < len(row):
                    day = as_date(row[date_col])
                    if (
                        day is not None
                        and known_2025_typo
                        and day.year == 2025
                        and day.month == 3
                    ):
                        day = day.replace(year=2026)
                if day is None:
                    day = fallback
                    if day is not None:
                        result["used_filename_date"] = True
                if day is None:
                    continue
                offline = row_has_offline(row)
                result["events"].append((prefix, day.isoformat(), offline))
                result["rows"] += 1
                if offline:
                    result["offline_rows"] += 1
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    finally:
        workbook.close()
    return result


def load_swaps() -> list[dict]:
    rows = []
    for line in SWAPS_TSV.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        while len(parts) < 5:
            parts.append("")
        garagem, nome, data_txt, prefixo, ident = parts[:5]
        day, month, year = (int(piece) for piece in data_txt.split("/"))
        rows.append(
            {
                "garagem": garagem,
                "nome": nome,
                "data": date(year, month, day),
                "prefixo": prefixo.strip(),
                "id": ident.strip(),
            }
        )
    return rows


def similar_prefix(prefix: str, known: set[str]) -> str:
    if prefix in known or len(prefix) < 4:
        return ""
    hits = sorted(item for item in known if item.startswith(prefix) and len(item) == len(prefix) + 1)
    if len(hits) == 1:
        return hits[0]
    return ""


def classify(days: int | None) -> str:
    if days is None:
        return ""
    for label, low, high in BUCKETS:
        if low <= days <= high:
            return label
    return ""


def fmt(day: date | None) -> str:
    if day is None:
        return ""
    return day.strftime("%d/%m/%Y")


def build_rows(swaps: list[dict], seen: dict[str, set[date]], offline: dict[str, set[date]]):
    known = set(seen)
    by_prefix: dict[str, list[date]] = defaultdict(list)
    for swap in swaps:
        by_prefix[swap["prefixo"]].append(swap["data"])
    for dates in by_prefix.values():
        dates.sort()

    detail = []
    for swap in swaps:
        prefix = swap["prefixo"]
        swap_day = swap["data"]
        seen_after = sorted(day for day in seen.get(prefix, ()) if day > swap_day)
        offline_after = sorted(day for day in offline.get(prefix, ()) if day > swap_day)
        later_swaps = [day for day in by_prefix[prefix] if day > swap_day]
        next_swap = later_swaps[0] if later_swaps else None

        first_seen = seen_after[0] if seen_after else None
        last_seen = seen_after[-1] if seen_after else None
        offline_day = offline_after[0] if offline_after else None
        days = (offline_day - swap_day).days if offline_day else None
        gap = (first_seen - swap_day).days if first_seen else None
        already = bool(offline_day and first_seen and offline_day == first_seen)

        if prefix not in known:
            situacao = "Prefixo não encontrado nos relatórios"
        elif not seen_after:
            situacao = "Prefixo sem linha nos relatórios depois da troca"
        elif offline_day is None:
            situacao = f"Sem OFFLINE até {fmt(last_seen)}"
        elif already:
            situacao = "OFFLINE já no primeiro relatório depois da troca"
        else:
            situacao = "OFFLINE"

        outra = ""
        if next_swap and (offline_day is None or next_swap < offline_day):
            outra = fmt(next_swap)

        detail.append(
            {
                **swap,
                "offline": offline_day,
                "dias": days,
                "faixa": classify(days),
                "situacao": situacao,
                "primeiro": first_seen,
                "ultimo": last_seen,
                "gap": gap,
                "ja_no_primeiro": "Sim" if already else ("Não" if offline_day else ""),
                "outra_troca": outra,
                "parecido": similar_prefix(prefix, known) if prefix not in known else "",
            }
        )
    return detail


def write_tsv(detail: list[dict]) -> None:
    header = [
        "Garagem",
        "Nome",
        "Data da troca",
        "Prefixo",
        "ID",
        "Data do OFFLINE",
        "Dias até o OFFLINE",
        "Faixa",
        "Situação",
        "1º relatório depois da troca",
        "Dias sem relatório depois da troca",
        "OFFLINE já no 1º relatório",
        "Último relatório do prefixo",
        "Outra troca antes do OFFLINE",
        "Prefixo parecido no relatório",
    ]
    lines = ["\t".join(header)]
    for row in detail:
        lines.append(
            "\t".join(
                [
                    row["garagem"],
                    row["nome"],
                    fmt(row["data"]),
                    row["prefixo"],
                    row["id"],
                    fmt(row["offline"]),
                    "" if row["dias"] is None else str(row["dias"]),
                    row["faixa"],
                    row["situacao"],
                    fmt(row["primeiro"]),
                    "" if row["gap"] is None else str(row["gap"]),
                    row["ja_no_primeiro"],
                    fmt(row["ultimo"]),
                    row["outra_troca"],
                    row["parecido"],
                ]
            )
        )
    OUT_TSV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def style_header(ws, columns: int) -> None:
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    thin = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    for col in range(1, columns + 1):
        cell = ws.cell(1, col)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = thin
    ws.auto_filter.ref = f"A1:{get_column_letter(columns)}{ws.max_row}"
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 32
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.oddHeader.left.text = "Troca de switch e primeiro OFFLINE"
    ws.oddFooter.right.text = "Página &P de &N"


def write_xlsx(detail: list[dict], summary: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Trocas"
    headers = [
        "Garagem",
        "Nome",
        "Data da troca",
        "Prefixo",
        "ID",
        "Data do OFFLINE",
        "Dias até o OFFLINE",
        "Faixa",
        "Situação",
        "1º relatório depois da troca",
        "Dias sem relatório depois da troca",
        "OFFLINE já no 1º relatório",
        "Último relatório do prefixo",
        "Outra troca antes do OFFLINE",
        "Prefixo parecido no relatório",
    ]
    ws.append(headers)
    fills = {
        "OFFLINE": PatternFill("solid", fgColor="FCE4D6"),
        "OFFLINE já no primeiro relatório depois da troca": PatternFill("solid", fgColor="F8CBAD"),
        "sem": PatternFill("solid", fgColor="E2EFDA"),
        "nao": PatternFill("solid", fgColor="F2F2F2"),
    }
    text_cols = {4, 5}
    date_cols = {3, 6, 10, 13}
    for row in detail:
        ws.append(
            [
                row["garagem"],
                row["nome"],
                row["data"],
                row["prefixo"],
                row["id"],
                row["offline"],
                row["dias"],
                row["faixa"],
                row["situacao"],
                row["primeiro"],
                row["gap"],
                row["ja_no_primeiro"],
                row["ultimo"],
                row["outra_troca"],
                row["parecido"],
            ]
        )
        excel_row = ws.max_row
        situacao = row["situacao"]
        if situacao == "OFFLINE":
            fill = fills["OFFLINE"]
        elif situacao.startswith("OFFLINE já"):
            fill = fills["OFFLINE já no primeiro relatório depois da troca"]
        elif situacao.startswith("Sem OFFLINE"):
            fill = fills["sem"]
        else:
            fill = fills["nao"]
        for col in range(1, len(headers) + 1):
            cell = ws.cell(excel_row, col)
            cell.fill = fill
            cell.font = Font(name="Calibri", size=11)
            cell.alignment = Alignment(vertical="center")
            if col in text_cols:
                cell.number_format = "@"
            if col in date_cols and cell.value:
                cell.number_format = "DD/MM/YYYY"
    style_header(ws, len(headers))
    widths = [32, 22, 16, 12, 12, 18, 18, 18, 52, 28, 30, 28, 26, 28, 30]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
    ws.page_setup.orientation = "landscape"
    ws.oddHeader.left.text = "Prefixos com troca de switch"
    ws.oddFooter.right.text = "Página &P de &N"
    ws.print_title_rows = "1:1"

    resumo = wb.create_sheet("Resumo")
    resumo["A1"] = "Faixa"
    resumo["B1"] = "Trocas"
    labels = [label for label, _, _ in BUCKETS] + [
        "Sem OFFLINE até o último relatório",
        "Sem linha depois da troca",
        "Prefixo não encontrado",
    ]
    counts = summary["faixas"]
    for index, label in enumerate(labels, start=2):
        resumo.cell(index, 1, label)
        resumo.cell(index, 2, counts[label])
        resumo.cell(index, 2).font = Font(name="Calibri", size=12)
        resumo.cell(index, 1).font = Font(name="Calibri", size=12)
    style_header(resumo, 2)
    resumo.column_dimensions["A"].width = 42
    resumo.column_dimensions["B"].width = 14
    resumo["D1"] = "Indicador"
    resumo["E1"] = "Valor"
    indicadores = [
        ("Trocas de switch", summary["trocas"]),
        ("Com OFFLINE depois da troca", summary["com_offline"]),
        ("Mediana dos dias até o OFFLINE", summary["mediana"]),
        ("Média dos dias até o OFFLINE", summary["media"]),
        ("OFFLINE já no 1º relatório seguinte", summary["ja_no_primeiro"]),
        ("Mediana quando houve relatório limpo antes", summary["mediana_depois"]),
        ("Sem OFFLINE até o último relatório", summary["faixas"]["Sem OFFLINE até o último relatório"]),
        ("Sem linha depois da troca", summary["faixas"]["Sem linha depois da troca"]),
        ("Prefixo não encontrado", summary["faixas"]["Prefixo não encontrado"]),
        ("Primeiro relatório lido", summary["primeiro_relatorio"]),
        ("Último relatório lido", summary["ultimo_relatorio"]),
    ]
    for index, (label, value) in enumerate(indicadores, start=2):
        resumo.cell(index, 4, label).font = Font(name="Calibri", size=12)
        resumo.cell(index, 5, value).font = Font(name="Calibri", size=12)
    for col in (4, 5):
        cell = resumo.cell(1, col)
        cell.fill = PatternFill("solid", fgColor="1F4E79")
        cell.font = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    resumo.column_dimensions["D"].width = 48
    resumo.column_dimensions["E"].width = 16

    chart = BarChart()
    chart.type = "col"
    chart.title = "Dias até o primeiro OFFLINE depois da troca do switch"
    chart.y_axis.title = "Trocas"
    chart.x_axis.title = None
    data = Reference(resumo, min_col=2, min_row=1, max_row=1 + len(labels))
    cats = Reference(resumo, min_col=1, min_row=2, max_row=1 + len(labels))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.legend = None
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    chart.y_axis.majorGridlines = None
    chart.style = 10
    chart.width = 22
    chart.height = 10
    resumo.add_chart(chart, "A12")

    info = wb.create_sheet("Leitura")
    info["A1"] = "Como ler"
    info["A1"].font = Font(bold=True, size=14, name="Calibri", color="1F4E79")
    notes = [
        "Entra como OFFLINE toda linha de relatório em que qualquer célula contém OFFLINE, em qualquer câmera. Célula vazia ou só \"-\" fica de fora.",
        "O prazo começa no dia seguinte à troca. Relatório do mesmo dia da manutenção não entra, porque pode ter sido gerado antes da substituição.",
        "Dias até o OFFLINE = data do primeiro relatório com OFFLINE menos a data da troca. Não é um monitoramento contínuo: só existem os dias em que saiu relatório.",
        "Quando o OFFLINE aparece já no primeiro relatório depois da troca, o problema pode ter começado antes, no intervalo sem relatório. A coluna \"Dias sem relatório depois da troca\" mostra esse intervalo.",
        "Não há relatório diário antes de fevereiro de 2026, fora o arquivo de 19/01 a 24/02. Trocas de 2025 podem acumular muitos dias só por falta de relatório.",
        "Cada troca conta sozinha. Se o mesmo prefixo trocou de novo antes do OFFLINE, a data dessa outra troca aparece na última coluna útil.",
        "\"1 ou + cam Off\" sem a palavra OFFLINE na linha não conta. O texto \"100% Offline\" conta. JSON com status offline também conta.",
        f"Relatórios lidos: {summary['arquivos_ok']} de {summary['arquivos']}. Falhas: {summary['arquivos_falha']}.",
        f"Cobertura dos relatórios: {summary['primeiro_relatorio']} a {summary['ultimo_relatorio']} ({summary['dias_de_relatorio']} dias com arquivo).",
        f"Trocas analisadas: {summary['trocas']}. Com OFFLINE depois: {summary['com_offline']}. Mediana dos dias, só entre quem teve OFFLINE: {summary['mediana']}.",
        f"OFFLINE já no primeiro relatório seguinte: {summary['ja_no_primeiro']}.",
    ]
    for index, note in enumerate(notes, start=3):
        info.cell(index, 1, note)
        info.cell(index, 1).alignment = Alignment(wrap_text=True, vertical="center")
        info.row_dimensions[index].height = 32
    info.column_dimensions["A"].width = 120
    info.page_setup.orientation = "landscape"
    info.page_setup.fitToPage = True
    info.page_setup.fitToWidth = 1
    info.page_setup.fitToHeight = 1
    info.page_setup.paperSize = info.PAPERSIZE_A4
    info.oddFooter.right.text = "Página &P de &N"

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    ART_XLSX.write_bytes(OUT_XLSX.read_bytes())


def write_png(counts: dict[str, int]) -> None:
    labels = list(counts)
    values = [counts[label] for label in labels]
    colors = ["#C65911", "#E07A3D", "#F4B183", "#F8CBAD", "#FCE4D6", "#548235", "#A6A6A6", "#7F7F7F"]
    fig, ax = plt.subplots(figsize=(12.5, 6.2), dpi=140)
    bars = ax.bar(range(len(labels)), values, color=colors[: len(labels)], width=0.72)
    ax.set_title("Dias até o primeiro OFFLINE depois da troca do switch", loc="left", fontsize=15, pad=14)
    ax.set_ylabel("Trocas")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=28, ha="right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.015, str(value), ha="center", va="bottom", fontsize=10)
    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG)
    plt.close(fig)


def main() -> None:
    files = json.loads(FILES_JSON.read_text(encoding="utf-8"))
    failures = ensure_downloads(files)
    print(f"arquivos {len(files)} falhas de download {len(failures)}", flush=True)

    seen: dict[str, set[date]] = defaultdict(set)
    offline: dict[str, set[date]] = defaultdict(set)
    report_days: set[date] = set()
    parsed_ok = 0
    parse_failures = list(failures)
    header_samples = []
    zero_row_files = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(parse_workbook, item): item for item in files}
        done = 0
        for future in as_completed(futures):
            item = futures[future]
            done += 1
            try:
                parsed = future.result()
            except Exception as exc:  # noqa: BLE001
                parse_failures.append({"id": item["id"], "name": item["name"], "error": str(exc)})
                continue
            if parsed["error"]:
                parse_failures.append({"id": item["id"], "name": item["name"], "error": parsed["error"]})
                continue
            parsed_ok += 1
            if parsed["rows"] == 0:
                zero_row_files.append(item["name"])
            if len(header_samples) < 12 and parsed["headers"]:
                header_samples.append({"name": item["name"], "headers": parsed["headers"]})
            for prefix, day_txt, is_offline in parsed["events"]:
                day = date.fromisoformat(day_txt)
                seen[prefix].add(day)
                report_days.add(day)
                if is_offline:
                    offline[prefix].add(day)
            if done % 40 == 0 or done == len(files):
                print(f"parse {done}/{len(files)}", flush=True)

    swaps = load_swaps()
    detail = build_rows(swaps, seen, offline)
    order = {
        "OFFLINE": 0,
        "OFFLINE já no primeiro relatório depois da troca": 1,
        "Sem OFFLINE": 2,
        "Prefixo sem linha": 3,
        "Prefixo não encontrado": 4,
    }

    def sort_key(row: dict):
        situacao = row["situacao"]
        group = 5
        for prefix, rank in order.items():
            if situacao.startswith(prefix):
                group = rank
                break
        return (group, row["dias"] if row["dias"] is not None else 10**9, row["data"], row["prefixo"])

    detail.sort(key=sort_key)

    faixa_counts = {label: 0 for label, _, _ in BUCKETS}
    faixa_counts["Sem OFFLINE até o último relatório"] = 0
    faixa_counts["Sem linha depois da troca"] = 0
    faixa_counts["Prefixo não encontrado"] = 0
    dias_list = []
    ja = 0
    for row in detail:
        if row["dias"] is not None:
            dias_list.append(row["dias"])
            faixa_counts[row["faixa"]] += 1
            if row["ja_no_primeiro"] == "Sim":
                ja += 1
        elif row["situacao"].startswith("Sem OFFLINE"):
            faixa_counts["Sem OFFLINE até o último relatório"] += 1
        elif row["situacao"].startswith("Prefixo sem linha"):
            faixa_counts["Sem linha depois da troca"] += 1
        else:
            faixa_counts["Prefixo não encontrado"] += 1

    summary = {
        "arquivos": len(files),
        "arquivos_ok": parsed_ok,
        "arquivos_falha": len(parse_failures),
        "falhas": parse_failures,
        "zero_row_files": zero_row_files,
        "header_samples": header_samples,
        "prefixos_vistos": len(seen),
        "prefixos_com_offline": len(offline),
        "dias_de_relatorio": len(report_days),
        "primeiro_relatorio": fmt(min(report_days)) if report_days else "",
        "ultimo_relatorio": fmt(max(report_days)) if report_days else "",
        "trocas": len(detail),
        "com_offline": len(dias_list),
        "ja_no_primeiro": ja,
        "mediana": statistics.median(dias_list) if dias_list else None,
        "media": round(statistics.mean(dias_list), 1) if dias_list else None,
        "mediana_depois": statistics.median(
            [row["dias"] for row in detail if row["dias"] is not None and row["ja_no_primeiro"] == "Não"]
        )
        if any(row["dias"] is not None and row["ja_no_primeiro"] == "Não" for row in detail)
        else None,
        "faixas": faixa_counts,
    }
    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(detail)
    write_xlsx(detail, summary)
    write_png(faixa_counts)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("arquivos_ok", "arquivos_falha", "trocas", "com_offline", "ja_no_primeiro", "mediana", "media", "primeiro_relatorio", "ultimo_relatorio", "faixas")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
