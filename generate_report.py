#!/usr/bin/env python3
"""Relatório executivo CFTV (Jotform) — layout profissional, Arial 12."""

from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
DATA_JOTFORM = ROOT / "data" / "jotform"
DATA_STATUS = ROOT / "data" / "status"
UPLOADS = [ROOT / "uploads"]
_extra_uploads = os.environ.get("REPORT_UPLOADS", "").strip()
if _extra_uploads:
    UPLOADS.append(Path(_extra_uploads))
OUT_PDF = ROOT / "reports" / "relatorio_executivo_cftv.pdf"

# Paleta neutra
NAVY = "#1F3340"
BLUE = "#2F5D73"
INK = "#1F2933"
MUTED = "#5C6B73"
CARD_BG = "#F3F5F7"
LINE = "#D7DEE3"
HEADER_BG = "#1F3340"
BAR_LIGHT = "#D9ECF5"

def _env_date(name: str, default: date) -> date:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return date.fromisoformat(raw)


PERIOD_START = _env_date("REPORT_PERIOD_START", date(2026, 9, 5))
PERIOD_END = _env_date("REPORT_PERIOD_END", date(2026, 11, 17))

SLOT_CAM = {
    "Problemas Detectados: Câm. Frontal": 21,
    "Problemas Detectados: Câm. Frente": 22,
    "Problemas Detectados: Câm. Corredor 1": 23,
    "Problemas Detectados: Câm. Corredor 2": 24,
    "Problemas Detectados: Câm. Corredor 3": 25,
    "Problemas Detectados: Câm. Corredor 4": 26,
}
ACT_CAM = {k.replace("Problemas Detectados", "Ações"): v for k, v in SLOT_CAM.items()}

# Mantém o detalhe do Jotform (não agrega categorias genéricas)
PROB_MAP = {
    "sem gravação de imagens": "Sem gravação de imagens",
    "câmera sem cartão de memória": "Câmera sem cartão de memória",
    "câmera inoperante": "Câmera inoperante / sem imagem",
    "câmera travada": "Câmera travada",
    "configuração incorreta da câmera": "Configuração incorreta da câmera",
    "câmera mal reposicionada": "Câmera mal reposicionada",
    "cabeamento rompido/danificado": "Cabeamento rompido/danificado",
    "falha na conexão dos cabos": "Falha na conexão dos cabos",
    "rj45 crimpado incorretamente": "RJ45 crimpado incorretamente",
    "switch apresentando falha": "Switch apresentando falha",
    "conexões do switch incorretas": "Conexões do switch incorretas",
    "switch não fixado corretamente": "Switch não fixado corretamente",
    "fusível queimado": "Fusível queimado",
    "câmera com infiltração": "Câmera com infiltração",
    "câmera desligada manualmente": "Câmera desligada manualmente",
    "câmera removida por terceiros": "Câmera removida por terceiros",
    "câmera não fixada corretamente": "Câmera não fixada corretamente",
    "câmera com sinal de vandalismo": "Câmera com sinal de vandalismo",
}
ACT_MAP = {
    "correção e ajuste da configuração da câmera": "Ajuste da configuração padrão da câmera",
    "normalização da gravação de imagens": "Formatação do cartão de memória",
    "reposicionamento adequado da câmera": "Reposicionamento adequado da câmera",
    "reinicialização da câmera": "Reinicialização da câmera (Reset)",
    "inserção ou substituição do cartão de memória": "Inserção ou substituição do cartão de memória",
    "ativação da câmera": "Ativação da Câmera (Câmera desconectada)",
    "crimpagem correta do conector rj45": "Crimpagem correta do conector RJ45",
    "correção na conexão dos cabos": "Correção na conexão dos cabos",
    "reparo do cabeamento": "Reparo do cabeamento",
    "substituição do cabeamento": "Substituição do cabeamento",
    "substituição do switch": "Substituição do switch",
    "correção da falha no switch": "Correção da falha no switch",
    "correção das conexões do switch": "Correção das conexões do switch",
    "substituição do fusível": "Substituição do fusível",
    "substituição da câmera defeituosa": "Substituição da câmera defeituosa",
    "câmera encaminhada para manutenção": "Câmera encaminhada para manutenção",
    "fixação adequada da câmera": "Fixação adequada da câmera",
    "fixação adequada do switch": "Fixação adequada do switch",
    "instalação da câmera removida": "Instalação da câmera removida",
}

# Agrupamento para tabelas e garagens
BUCKET_CABEAMENTO = {
    "Cabeamento rompido/danificado",
    "Falha na conexão dos cabos",
    "RJ45 crimpado incorretamente",
}
BUCKET_SWITCH = {
    "Switch apresentando falha",
    "Conexões do switch incorretas",
    "Switch não fixado corretamente",
}
BUCKET_CARTAO = {
    "Sem gravação de imagens",
    "Câmera sem cartão de memória",
}
BUCKET_CAMERA = {
    "Câmera inoperante / sem imagem",
    "Câmera inoperante",
    "Câmera travada",
    "Configuração incorreta da câmera",
    "Câmera mal reposicionada",
    "Câmera com infiltração",
    "Câmera desligada manualmente",
    "Câmera removida por terceiros",
    "Câmera não fixada corretamente",
    "Câmera com sinal de vandalismo",
    "Fusível queimado",
}

ACT_BUCKET_CABEAMENTO = {
    "Crimpagem correta do conector RJ45",
    "Correção na conexão dos cabos",
    "Reparo do cabeamento",
    "Substituição do cabeamento",
}
ACT_BUCKET_SWITCH = {
    "Substituição do switch",
    "Correção da falha no switch",
    "Correção das conexões do switch",
    "Fixação adequada do switch",
}
ACT_BUCKET_CARTAO = {
    "Formatação do cartão de memória",
    "Inserção ou substituição do cartão de memória",
    "Normalização da gravação de imagens",  # legado
}
ACT_BUCKET_CAMERA = {
    "Ajuste da configuração padrão da câmera",
    "Correção e ajuste da configuração da câmera",  # legado
    "Reposicionamento adequado da câmera",
    "Reinicialização da câmera (Reset)",
    "Reinicialização da câmera",  # legado
    "Ativação da Câmera (Câmera desconectada)",
    "Ativação da câmera",  # legado
    "Substituição da câmera defeituosa",
    "Câmera encaminhada para manutenção",
    "Fixação adequada da câmera",
    "Instalação da câmera removida",
    "Substituição do fusível",
}


def problem_bucket(label: str) -> str:
    if label in BUCKET_CABEAMENTO:
        return "Cabeamento"
    if label in BUCKET_SWITCH:
        return "Switch"
    if label in BUCKET_CARTAO:
        return "Cartão de Memória"
    if label in BUCKET_CAMERA or label.lower().startswith("câmera") or label.lower().startswith("camera"):
        return "Câmera"
    return "Câmera"


def action_bucket(label: str) -> str:
    if label in ACT_BUCKET_CABEAMENTO:
        return "Cabeamento"
    if label in ACT_BUCKET_SWITCH:
        return "Switch"
    if label in ACT_BUCKET_CARTAO or "cartão" in label.lower() or "cartao" in label.lower():
        return "Cartão de Memória"
    return "Câmera"


def aggregate_by_bucket(items: list[tuple[str, int]], kind: str) -> list[tuple[str, int]]:
    """Soma por bucket; mantém detalhes não agrupados abaixo se necessário — aqui só buckets."""
    bucket_fn = problem_bucket if kind == "problem" else action_bucket
    c: Counter[str] = Counter()
    for label, qty in items:
        c[bucket_fn(label)] += qty
    order = ["Cartão de Memória", "Câmera", "Cabeamento", "Switch"]
    return [(k, c[k]) for k in order if c.get(k)] + [(k, v) for k, v in c.most_common() if k not in order]
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}


def register_fonts() -> None:
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from font_paths import liberation_pair

    regular, bold = liberation_pair()
    pdfmetrics.registerFont(TTFont("Arial", regular))
    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))


def parse_date(value) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    try:
        return pd.to_datetime(text, format="%d/%m/%Y")
    except ValueError:
        pass
    match = re.search(
        r"(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(\d{1,2}),\s*(\d{4})",
        text,
        re.I,
    )
    if match:
        return pd.Timestamp(
            year=int(match.group(3)),
            month=MONTHS[match.group(1).lower()],
            day=int(match.group(2)),
        )
    return pd.to_datetime(text, dayfirst=True, errors="coerce")


def split_multi(value) -> list[str]:
    if pd.isna(value):
        return []
    out = []
    for part in str(value).replace("\r", "\n").split("\n"):
        part = part.strip(" -;\t")
        if part:
            out.append(part)
    return out


def norm_problem(text: str) -> str | None:
    key = text.strip().lower()
    if not key or key.startswith("nenhuma anomalia"):
        return None
    return PROB_MAP.get(key, text.strip())


def norm_action(text: str) -> str | None:
    key = text.strip().lower()
    if not key or key.startswith("nenhuma ação") or key.startswith("nenhuma acao"):
        return None
    return ACT_MAP.get(key, text.strip())


def extract_cameras(text: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\b(2[1-6])\b", text)})


def infer_from_observation(text: str) -> tuple[list[str], list[str], list[int]]:
    """Interpreta 100% do texto da observação (contexto, não só keyword)."""
    raw = text
    t = text.lower()
    cams = extract_cameras(raw)
    problems: list[str] = []
    actions: list[str] = []

    def add_p(label: str) -> None:
        if label not in problems:
            problems.append(label)

    def add_a(label: str) -> None:
        if label not in actions:
            actions.append(label)

    # --- Problemas (rótulos específicos, alinhados ao Jotform) ---
    if re.search(r"fus[ií]ve(?:l|is).{0,40}(queim|troc|substitu|danific)", t) or re.search(
        r"(queim|troc|substitu).{0,40}fus[ií]ve", t
    ):
        add_p("Fusível queimado")
    # "swith" cobre typo comum nas observações
    if "switch" in t or "swith" in t:
        if any(k in t for k in ["não fix", "nao fix", "solto", "fixa"]):
            add_p("Switch não fixado corretamente")
        elif any(k in t for k in ["conexão", "conexao", "porta", "poe"]):
            add_p("Conexões do switch incorretas")
        elif any(
            k in t
            for k in [
                "queim",
                "curto",
                "água",
                "agua",
                "oxid",
                "falha",
                "danific",
                "apag",
                "troca",
                "substitu",
                "novo",
                "utiliz",
            ]
        ):
            # troca/substituição implica falha no switch (mesmo sem a palavra "falha")
            add_p("Switch apresentando falha")
        else:
            add_p("Switch apresentando falha")
    if any(k in t for k in ["rj45", "rj 45", "crimp"]):
        add_p("RJ45 crimpado incorretamente")
    elif any(k in t for k in ["cabo", "cabeamento"]) and any(
        k in t for k in ["romp", "danific", "oxid", "cortad"]
    ):
        add_p("Cabeamento rompido/danificado")
    elif any(k in t for k in ["cabo", "conector", "negativo"]) and any(
        k in t for k in ["conexão", "conexao", "deslig", "desconect", "mal contato", "incorret"]
    ):
        add_p("Falha na conexão dos cabos")
    if any(k in t for k in ["sem cartão", "sem cartao", "sem sd", "cartão ausente", "cartao ausente"]):
        add_p("Câmera sem cartão de memória")
    elif any(k in t for k in ["cartão", "cartao", " sd", "sd ", "formata"]) and any(
        k in t for k in ["sd", "cartão", "cartao", "grav", "anomal", "troc", "formata"]
    ):
        add_p("Sem gravação de imagens")
    if any(k in t for k in ["sem grav", "não grav", "nao grav", "sem gravar", "não voltou a gravar", "nao voltou a gravar"]):
        add_p("Sem gravação de imagens")
    if any(k in t for k in ["reposicion", "fora de posição", "fora de posicao", "virada", "ajuste de imagem", "adesivo"]):
        add_p("Câmera mal reposicionada")
    if any(k in t for k in ["ip ", "ips ", "configura"]) and any(
        k in t for k in ["incorret", "errad", "ajuste", "conflito", "como 100", "errado"]
    ):
        add_p("Configuração incorreta da câmera")
    if any(k in t for k in ["terceiro", "retirada", "removida", "roub"]):
        if any(k in t for k in ["câmera", "camera", "cam "]):
            add_p("Câmera removida por terceiros")
    if "vandal" in t:
        add_p("Câmera com sinal de vandalismo")
    if any(
        k in t
        for k in [
            "com defeito",
            "sem comunicação",
            "sem comunicacao",
            "não dá acesso",
            "nao da acesso",
            "inoperante",
            "sem imagem",
            "sem sinal",
            "sem video",
            "sem vídeo",
            "não acess",
            "nao acess",
            "instabilidade",
        ]
    ):
        add_p("Câmera inoperante / sem imagem")
    if any(k in t for k in ["travad", "travou"]):
        add_p("Câmera travada")
    if "infiltra" in t or (("água" in t or "agua" in t) and any(k in t for k in ["câmera", "camera", "case"])):
        add_p("Câmera com infiltração")
    if any(k in t for k in ["desligad", "apagad"]) and any(k in t for k in ["câmera", "camera", "manual"]):
        add_p("Câmera desligada manualmente")
    if any(k in t for k in ["não fix", "nao fix", "solta", "fixação", "fixacao"]) and any(
        k in t for k in ["câmera", "camera"]
    ):
        add_p("Câmera não fixada corretamente")

    # --- Ações ---
    if any(k in t for k in ["formata", "troca do cartão", "troca do cartao", "troca cartão", "troca cartao", "cartão sd", "cartao sd", "substitu"]):
        if any(k in t for k in ["sd", "cartão", "cartao", "memória", "memoria"]):
            add_a("Inserção ou substituição do cartão de memória")
            add_a("Formatação do cartão de memória")
    if any(k in t for k in ["reset", "reinic", "reboot"]):
        add_a("Reinicialização da câmera (Reset)")
    if any(k in t for k in ["crimp", "refeito rj", "refeita a crimp", "refeito o rj"]):
        add_a("Crimpagem correta do conector RJ45")
    elif any(k in t for k in ["substitu"]) and any(k in t for k in ["cabo", "cabeamento"]):
        add_a("Substituição do cabeamento")
    elif any(k in t for k in ["reparo", "refeito", "refeita"]) and any(k in t for k in ["cabo", "cabeamento"]):
        add_a("Reparo do cabeamento")
    elif any(k in t for k in ["conexão", "conexao", "conector", "negativo"]) and any(
        k in t for k in ["cabo", "correção", "correcao", "ajuste"]
    ):
        add_a("Correção na conexão dos cabos")
    if "switch" in t or "swith" in t:
        if any(k in t for k in ["troca", "substitu", "novo", "utiliz"]):
            add_a("Substituição do switch")
        elif any(k in t for k in ["conexão", "conexao", "porta", "poe"]):
            add_a("Correção das conexões do switch")
        elif any(k in t for k in ["correção", "correcao", "falha", "fixa"]):
            add_a("Correção da falha no switch")
        else:
            add_a("Correção da falha no switch")
    if re.search(r"(troc|substitu).{0,30}fus[ií]ve", t) or re.search(r"fus[ií]ve.{0,30}(troc|substitu)", t):
        add_a("Substituição do fusível")
    if re.search(r"encaminh.{0,30}(c[aâ]mera|camera|manuten)", t):
        add_a("Câmera encaminhada para manutenção")
    elif re.search(r"(troca|substitui[cç][aã]o).{0,25}(c[aâ]mera|camera)", t) or re.search(
        r"(c[aâ]mera|camera).{0,25}(troc|substitu|nova)", t
    ):
        add_a("Substituição da câmera defeituosa")
    if "reposicion" in t:
        add_a("Reposicionamento adequado da câmera")
    if "configura" in t or "ip " in t:
        add_a("Ajuste da configuração padrão da câmera")
    if "fixa" in t and ("switch" in t or "swith" in t):
        add_a("Fixação adequada do switch")
    elif "fixa" in t:
        add_a("Fixação adequada da câmera")
    if any(k in t for k in ["instal"]) and any(k in t for k in ["removid", "retirad"]):
        add_a("Instalação da câmera removida")
    if any(k in t for k in ["ajuste de imagem", "normaliz", "formata"]) and "grav" in t:
        add_a("Formatação do cartão de memória")
    if any(k in t for k in ["ativa", "ligou", "ligado"]) and any(k in t for k in ["câmera", "camera"]):
        add_a("Ativação da Câmera (Câmera desconectada)")

    return problems, actions, cams


def discover_jotform() -> list[Path]:
    files = sorted(DATA_JOTFORM.glob("*.xlsx"))
    if files:
        return files
    for folder in UPLOADS:
        files = sorted(folder.glob("Revis*.xlsx"))
        if files:
            return files
    raise FileNotFoundError("Arquivos Jotform não encontrados.")


def discover_status_files() -> list[Path]:
    # Prioriza bases de telemetria do usuário (BQ / cftv_28-09...), não o consolidado de outra frota
    patterns = [
        "cftv_28-09*",
        "*bq-results*",
        "bq-results*.csv",
    ]
    found: list[Path] = []
    search_dirs = [DATA_STATUS, ROOT / "data", ROOT / "uploads", *UPLOADS]
    for folder in search_dirs:
        if not folder.exists():
            continue
        for pat in patterns:
            found.extend(folder.glob(pat))
            found.extend(folder.rglob(pat))
    found = [
        p
        for p in found
        if p.is_file()
        and "Revis" not in p.name
        and "jotform" not in str(p).lower()
        and "consolidado_cftv" not in p.name.lower()
    ]
    uniq = {}
    for p in found:
        uniq[p.resolve()] = p
    return sorted(uniq.values(), key=lambda p: p.name)


def _pick_col(columns: list[str], candidates: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    for c in columns:
        cl = c.lower()
        for cand in candidates:
            if cand in cl:
                return c
    return None


def load_status_frame() -> pd.DataFrame | None:
    files = discover_status_files()
    if not files:
        return None
    frames = []
    for path in files:
        try:
            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
        except Exception:
            continue
        if df.empty:
            continue
        prefix_col = _pick_col(list(df.columns), ["prefixo_veiculo", "prefixo", "prefix"])
        login_col = _pick_col(list(df.columns), ["login"])
        sd_col = _pick_col(list(df.columns), ["sdcard", "sd_card", "cartao", "cartão"])
        ts_col = _pick_col(list(df.columns), ["timestamp", "data_hora", "datetime", "ts", "data"])
        if not prefix_col or not login_col or not sd_col:
            continue
        part = pd.DataFrame(
            {
                "prefixo": pd.to_numeric(df[prefix_col], errors="coerce"),
                "login": df[login_col].astype(str).str.strip().str.lower(),
                "sdcard": df[sd_col].astype(str).str.strip().str.lower(),
            }
        )
        if ts_col:
            part["ts"] = pd.to_datetime(df[ts_col], utc=True, format="mixed", errors="coerce")
        else:
            part["ts"] = pd.NaT
        part = part.dropna(subset=["prefixo"])
        part["prefixo"] = part["prefixo"].astype(int)
        part["_file"] = path.name
        frames.append(part)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def vehicle_resolution(status: pd.DataFrame | None) -> dict[int, str]:
    """resolvido = login ok e sdcard ok (última medição do veículo)."""
    if status is None or status.empty:
        return {}
    df = status.copy()
    if df["ts"].notna().any():
        df = df.sort_values("ts")
        latest = df.groupby("prefixo", as_index=False).tail(20)  # últimas leituras
        # pega o timestamp máximo por prefixo e filtra
        max_ts = df.groupby("prefixo")["ts"].transform("max")
        latest = df[df["ts"].isna() | (df["ts"] == max_ts)]
    else:
        latest = df

    out: dict[int, str] = {}
    for prefixo, g in latest.groupby("prefixo"):
        login_ok = g["login"].eq("ok")
        sd_ok = g["sdcard"].eq("ok")
        if login_ok.any() and (login_ok & sd_ok).all() and login_ok.all():
            out[int(prefixo)] = "resolvido"
        elif (~login_ok).all():
            out[int(prefixo)] = "offline"
        else:
            out[int(prefixo)] = "nao_resolvido"
    return out


def load_maintenances() -> pd.DataFrame:
    frames = []
    for path in discover_jotform():
        part = pd.read_excel(path)
        part["_source_file"] = path.name
        frames.append(part)
    raw = pd.concat(frames, ignore_index=True)
    raw["_data"] = raw["Data"].map(parse_date)
    raw["_envio"] = raw["Data de Envio"].map(parse_date)
    raw["_ref"] = raw["_data"].fillna(raw["_envio"])
    dedup = raw.sort_values(["ID do Envio", "_source_file"]).drop_duplicates("ID do Envio", keep="last")
    period = dedup[
        (dedup["_ref"] >= pd.Timestamp(PERIOD_START))
        & (dedup["_ref"] <= pd.Timestamp(f"{PERIOD_END} 23:59:59"))
    ].copy()
    period["Garagem"] = period["Garagem"].fillna("Não identificado").astype(str).str.strip()
    period["Prefixo"] = pd.to_numeric(period["Prefixo"], errors="coerce").astype("Int64")
    period["_day"] = period["_ref"].dt.date
    period.attrs["raw_rows"] = len(raw)
    period.attrs["dedup_rows"] = len(dedup)
    return period.reset_index(drop=True)


@dataclass
class Occurrence:
    submission_id: int
    prefixo: int | None
    garagem: str
    day: date
    camera: int | None
    kind: str
    label: str
    source: str


@dataclass
class ReportData:
    maints: pd.DataFrame
    problems: list[Occurrence]
    actions: list[Occurrence]
    n_maints: int
    n_reinc: int
    n_prefix: int
    n_garages: int
    n_cameras_retirada: int
    garage_rows: list[tuple[str, int, int]]
    top_problems: list[tuple[str, int]]
    top_actions: list[tuple[str, int]]
    top_problem_buckets: list[tuple[str, int]]
    top_action_buckets: list[tuple[str, int]]
    garage_bucket_problems: list[tuple[str, list[tuple[str, int]]]]


def _cam_key(occ: Occurrence) -> tuple:
    """Unidade câmera: slot dentro da OS. Sem slot → 1 unidade por OS+label."""
    if occ.camera is not None:
        return (occ.submission_id, occ.camera)
    return (occ.submission_id, f"na:{occ.label}")


def _prefix_key(occ: Occurrence) -> tuple:
    """Unidade veículo: prefixo (fallback OS se prefixo ausente)."""
    if occ.prefixo is not None:
        return ("p", occ.prefixo)
    return ("s", occ.submission_id)


def count_cameras_by_label(items: list[Occurrence]) -> list[tuple[str, int]]:
    """Câmeras distintas (OS + slot) por rótulo."""
    by: dict[str, set] = defaultdict(set)
    for it in items:
        by[it.label].add(_cam_key(it))
    return sorted(((lab, len(keys)) for lab, keys in by.items()), key=lambda x: (-x[1], x[0]))


def count_vehicles_by_bucket(items: list[Occurrence], kind: str) -> list[tuple[str, int]]:
    """Prefixos distintos por grupo. Um veículo com vários problemas do grupo conta 1."""
    bucket_fn = problem_bucket if kind == "problem" else action_bucket
    by: dict[str, set] = defaultdict(set)
    for it in items:
        by[bucket_fn(it.label)].add(_prefix_key(it))
    order = ["Cartão de Memória", "Câmera", "Cabeamento", "Switch"]
    out = [(k, len(by[k])) for k in order if by.get(k)]
    out += [(k, len(v)) for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])) if k not in order]
    return out


RETIRADA_MARKERS = (
    "removida por terceiros",
    "sem câmera",
    "sem camera",
    "câmera retirada",
    "camera retirada",
    "câmera removida",
    "camera removida",
)


def count_cameras_retirada(df: pd.DataFrame) -> int:
    """Por formulário/OS: slots marcados como sem câmera / câmera retirada."""
    keys: set[tuple] = set()
    for _, row in df.iterrows():
        sid = int(row["ID do Envio"])
        for col, cam in SLOT_CAM.items():
            text = str(row.get(col) or "").lower()
            if any(m in text for m in RETIRADA_MARKERS):
                keys.add((sid, cam))
        obs = str(row.get("Observações") or "")
        if not obs or obs.lower() == "nan":
            continue
        low = obs.lower()
        # padrões explícitos de ausência (evita "cartão retirado" / bloco MAC RETIRADA)
        for m in re.finditer(
            r"(?:c[aâ]mera|cam)\s*(2[1-6]).{0,40}(?:retirad\w*\s+por\s+terceiros|removid\w*\s+por\s+terceiros|sem\s+c[aâ]mera)",
            low,
            re.I,
        ):
            keys.add((sid, int(m.group(1))))
        for m in re.finditer(
            r"(?:retirad\w*|removid\w*)\s+por\s+terceiros.{0,25}(?:c[aâ]mera|cam)\s*(2[1-6])",
            low,
            re.I,
        ):
            keys.add((sid, int(m.group(1))))
        if re.search(r"sem\s+c[aâ]mera", low) and not re.search(r"2[1-6]", low):
            # menção genérica sem slot → 1 por OS
            keys.add((sid, "na:sem_camera"))
    return len(keys)


def build_occurrences(df: pd.DataFrame) -> tuple[list[Occurrence], list[Occurrence]]:
    problems: list[Occurrence] = []
    actions: list[Occurrence] = []
    seen_p: set[tuple] = set()
    seen_a: set[tuple] = set()

    def add_prob(sid, prefixo, garagem, day, cam, label, source):
        key = (sid, cam, label)
        if key in seen_p:
            return
        # evita duplicar label já capturado em outra câmera da mesma OS quando cam é None
        if cam is None and any(s == sid and l == label for s, _, l in seen_p):
            return
        seen_p.add(key)
        problems.append(Occurrence(sid, prefixo, garagem, day, cam, "problem", label, source))

    def add_act(sid, prefixo, garagem, day, cam, label, source):
        key = (sid, cam, label)
        if key in seen_a:
            return
        if cam is None and any(s == sid and l == label for s, _, l in seen_a):
            return
        seen_a.add(key)
        actions.append(Occurrence(sid, prefixo, garagem, day, cam, "action", label, source))

    for _, row in df.iterrows():
        sid = int(row["ID do Envio"])
        prefixo = int(row["Prefixo"]) if pd.notna(row["Prefixo"]) else None
        garagem = str(row["Garagem"])
        day = row["_day"]

        for col, cam in SLOT_CAM.items():
            for raw in split_multi(row.get(col)):
                label = norm_problem(raw)
                if label:
                    add_prob(sid, prefixo, garagem, day, cam, label, "structured")
        for col, cam in ACT_CAM.items():
            for raw in split_multi(row.get(col)):
                label = norm_action(raw)
                if label:
                    add_act(sid, prefixo, garagem, day, cam, label, "structured")

        obs = row.get("Observações")
        has_obs = not (pd.isna(obs) or not str(obs).strip())
        if has_obs:
            # SEMPRE analisa a observação completa
            inf_probs, inf_acts, cams = infer_from_observation(str(obs))
            target_cams = cams or [None]
            for label in inf_probs:
                for cam in target_cams:
                    add_prob(sid, prefixo, garagem, day, cam, label, "observation")
            for label in inf_acts:
                for cam in target_cams:
                    add_act(sid, prefixo, garagem, day, cam, label, "observation")

        # Coluna "Switch Utilizado" > 0 = troca/uso de switch na OS
        try:
            switch_used = float(row.get("Switch Utilizado") or 0)
        except (TypeError, ValueError):
            switch_used = 0.0
        if switch_used > 0:
            add_prob(
                sid,
                prefixo,
                garagem,
                day,
                None,
                "Switch apresentando falha",
                "switch_utilizado",
            )
            add_act(
                sid,
                prefixo,
                garagem,
                day,
                None,
                "Substituição do switch",
                "switch_utilizado",
            )

    return problems, actions


def analyze(df: pd.DataFrame) -> ReportData:
    problems, actions = build_occurrences(df)

    visits = df["Prefixo"].value_counts()
    n_reinc = int((visits[visits >= 2] - 1).sum())

    garage_reinc_counter: Counter[str] = Counter()
    for prefixo, group in df.groupby("Prefixo"):
        if len(group) < 2:
            continue
        ordered = group.sort_values("_ref")
        for _, row in ordered.iloc[1:].iterrows():
            garage_reinc_counter[str(row["Garagem"])] += 1

    garage_maints = Counter(df["Garagem"])
    garage_rows = [
        (garagem, garage_maints[garagem], garage_reinc_counter.get(garagem, 0))
        for garagem in sorted(garage_maints.keys(), key=lambda s: s.casefold())
    ]

    # Garagem / grupo: por prefixo (veículo)
    garage_bucket_veic: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for p in problems:
        garage_bucket_veic[p.garagem][problem_bucket(p.label)].add(_prefix_key(p))
    bucket_order = ["Cabeamento", "Switch", "Câmera", "Cartão de Memória"]
    garage_bucket_problems = []
    for garagem, _, _ in garage_rows:
        counts = garage_bucket_veic[garagem]
        tops = [(b, len(counts[b])) for b in bucket_order if counts.get(b)]
        garage_bucket_problems.append((garagem, tops))

    top_problems = count_cameras_by_label(problems)
    top_actions = count_cameras_by_label(actions)

    return ReportData(
        maints=df,
        problems=problems,
        actions=actions,
        n_maints=len(df),
        n_reinc=n_reinc,
        n_prefix=int(df["Prefixo"].nunique()),
        n_garages=int(df["Garagem"].nunique()),
        n_cameras_retirada=count_cameras_retirada(df),
        garage_rows=garage_rows,
        top_problems=top_problems,
        top_actions=top_actions,
        top_problem_buckets=count_vehicles_by_bucket(problems, "problem"),
        top_action_buckets=count_vehicles_by_bucket(actions, "action"),
        garage_bucket_problems=garage_bucket_problems,
    )


def header(c: canvas.Canvas, width: float, height: float, title: str) -> float:
    # Fundo branco explícito (evita preview preto em tema escuro)
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(HexColor(HEADER_BG))
    c.rect(0, height - 36, width, 36, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 12)
    c.drawString(36, height - 23, title)
    return height - 56


def page_num(c: canvas.Canvas, width: float, page: int, total: int = 3) -> None:
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 10)
    c.drawRightString(width - 36, 16, f"{page} / {total}")


def kpi_card(c, x, y, w, h, label, value):
    c.setFillColor(HexColor(CARD_BG))
    c.roundRect(x, y - h, w, h, 6, fill=1, stroke=0)
    c.setFillColor(HexColor(BLUE))
    c.roundRect(x, y - h, 5, h, 2, fill=1, stroke=0)
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 10)
    c.drawString(x + 16, y - 20, label)
    c.setFillColor(HexColor(NAVY))
    text = value if isinstance(value, str) else f"{value:,}".replace(",", ".")
    c.setFont("Arial-Bold", 18 if len(str(text)) < 14 else 14)
    c.drawString(x + 16, y - 46, str(text))


def draw_table(c, x, y, col_ws, headers, rows, row_h=22, center_cols: set[int] | None = None):
    """Tabela plana (sem sombra / 3D)."""
    center_cols = center_cols or set()
    table_w = sum(col_ws)
    header_h = 24

    c.setFillColor(HexColor(HEADER_BG))
    c.rect(x, y - header_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 10)
    cx = x
    for j, (w, h) in enumerate(zip(col_ws, headers)):
        if j in center_cols:
            c.drawCentredString(cx + w / 2, y - 16, h)
        else:
            c.drawString(cx + 10, y - 16, h)
        cx += w
    y -= header_h

    for i, row in enumerate(rows):
        bg = white if i % 2 == 0 else HexColor("#F5F7F9")
        c.setFillColor(bg)
        c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#E6EBEE"))
        c.setLineWidth(0.5)
        c.line(x, y - row_h, x + table_w, y - row_h)
        c.setFillColor(HexColor(INK))
        cx = x
        text_y = y - row_h / 2 - 3.5
        for j, (w, val) in enumerate(zip(col_ws, row)):
            text = f"{val:,}".replace(",", ".") if isinstance(val, int) else str(val)
            if j in center_cols:
                c.setFont("Arial", 10)
                c.drawCentredString(cx + w / 2, text_y, text)
            else:
                c.setFont("Arial", 10)
                c.drawString(cx + 10, text_y, text)
            cx += w
        y -= row_h
    return y


def page1(c, width, height, data: ReportData):
    y = header(c, width, height, "Relatório Executivo CFTV — Manutenções")
    period_label = f"{PERIOD_START.strftime('%d/%m')} a {PERIOD_END.strftime('%d/%m/%Y')}"
    cards = [
        ("Período", period_label),
        ("Manutenções", data.n_maints),
        ("Reincidências", data.n_reinc),
        ("Câmeras retirada", data.n_cameras_retirada),
    ]
    gap = 14
    card_w = (width - 72 - 3 * gap) / 4
    card_h = 62
    for i, (label, value) in enumerate(cards):
        kpi_card(c, 36 + i * (card_w + gap), y, card_w, card_h, label, value)

    y -= card_h + 22
    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 12)
    c.drawString(36, y, "Resumo por garagem")
    y -= 14

    rows = [
        (g, m, r, f"{(r / m * 100) if m else 0.0:.1f}%".replace(".", ","))
        for g, m, r in data.garage_rows
    ]
    draw_table(
        c,
        36,
        y,
        [380, 120, 130, 130],
        ["Garagem", "Manutenções", "Reincidências", "% Reincidência"],
        rows,
        row_h=24,
        center_cols={1, 2, 3},
    )
    page_num(c, width, 1)


def draw_bar_table(
    c: canvas.Canvas,
    x: float,
    y: float,
    title: str,
    item_header: str,
    rows: list[tuple[str, int]],
    table_w: float = 360,
    subtitle: str | None = None,
) -> float:
    """Tabela com barra azul clara na quantidade (unidade = câmeras na OS)."""
    label_w = table_w * 0.52
    qty_w = table_w * 0.22
    bar_w = table_w * 0.26
    row_h = 22
    header_h = 22
    max_val = max((q for _, q in rows), default=1)

    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 12)
    c.drawString(x, y, title)
    y -= 11
    if subtitle:
        c.setFillColor(HexColor(MUTED))
        c.setFont("Arial", 8)
        c.drawString(x, y, subtitle)
        y -= 12
    else:
        y -= 2

    c.setFillColor(HexColor(HEADER_BG))
    c.roundRect(x, y - header_h, table_w, header_h, 3, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Arial-Bold", 10)
    c.drawString(x + 8, y - 15, item_header)
    c.drawRightString(x + label_w + qty_w - 6, y - 15, "Quantidade")
    y -= header_h

    for i, (label, qty) in enumerate(rows):
        bg = white if i % 2 == 0 else HexColor(CARD_BG)
        c.setFillColor(bg)
        c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)

        c.setFillColor(HexColor(INK))
        c.setFont("Arial", 9)
        text = label if len(label) <= 40 else label[:37] + "…"
        c.drawString(x + 8, y - 15, text)
        c.setFont("Arial-Bold", 10)
        c.drawRightString(x + label_w + qty_w - 6, y - 15, f"{qty:,}".replace(",", "."))

        filled = (qty / max_val) * (bar_w - 14) if max_val else 0
        bar_x = x + label_w + qty_w + 4
        bar_y = y - row_h + 7
        c.setFillColor(HexColor("#EEF5F8"))
        c.roundRect(bar_x, bar_y, bar_w - 14, 8, 2, fill=1, stroke=0)
        c.setFillColor(HexColor(BAR_LIGHT))
        c.roundRect(bar_x, bar_y, max(filled, 2), 8, 2, fill=1, stroke=0)
        y -= row_h
    return y


def page2(c, width, height, data: ReportData):
    y = header(c, width, height, "Principais problemas e ações")

    left_x = 36
    right_x = 450
    table_w = 360

    y_left = draw_bar_table(
        c,
        left_x,
        y,
        "Problemas por Grupo — Veículo",
        "Grupo",
        data.top_problem_buckets,
        table_w=table_w,
        subtitle="Quantidade = prefixos distintos com ≥1 problema do grupo",
    )
    y_right = draw_bar_table(
        c,
        right_x,
        y,
        "Ações por Grupo — Veículo",
        "Grupo",
        data.top_action_buckets,
        table_w=table_w,
        subtitle="Quantidade = prefixos distintos com ≥1 ação do grupo",
    )

    y = min(y_left, y_right) - 36
    draw_bar_table(
        c,
        left_x,
        y,
        "Problemas mais identificados — Câmera",
        "Problema",
        data.top_problems[:9],
        table_w=table_w,
        subtitle="Quantidade = câmeras (slot na OS) com aquele problema",
    )
    draw_bar_table(
        c,
        right_x,
        y,
        "Ações mais realizadas — Câmera",
        "Ação",
        data.top_actions[:9],
        table_w=table_w,
        subtitle="Quantidade = câmeras (slot na OS) com aquela ação",
    )
    page_num(c, width, 2)


def page3(c, width, height, data: ReportData):
    y = header(c, width, height, "Principais problemas por garagem")

    c.setFillColor(HexColor(NAVY))
    c.setFont("Arial-Bold", 12)
    c.drawString(36, y, "Veículos (prefixos) por grupo em cada garagem")
    y -= 12
    c.setFillColor(HexColor(MUTED))
    c.setFont("Arial", 8)
    c.drawString(36, y, "Quantidade = prefixos distintos com ≥1 problema do grupo")
    y -= 14

    bucket_order = ["Cabeamento", "Switch", "Câmera", "Cartão de Memória"]
    rows = []
    for garagem, tops in data.garage_bucket_problems:
        cmap = dict(tops)
        total = sum(cmap.get(b, 0) for b in bucket_order)
        rows.append(
            (
                garagem,
                cmap.get("Cabeamento", 0),
                cmap.get("Switch", 0),
                cmap.get("Câmera", 0),
                cmap.get("Cartão de Memória", 0),
                total,
            )
        )

    draw_table(
        c,
        36,
        y,
        [280, 90, 80, 90, 130, 80],
        ["Garagem", "Cabeamento", "Switch", "Câmera", "Cartão de Memória", "Total"],
        rows,
        row_h=22,
        center_cols={1, 2, 3, 4, 5},
    )
    page_num(c, width, 3)


def build_pdf(data: ReportData) -> Path:
    register_fonts()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A4)
    c = canvas.Canvas(str(OUT_PDF), pagesize=landscape(A4))
    c.setTitle(f"Relatório Executivo CFTV — {PERIOD_START.strftime('%d/%m')} a {PERIOD_END.strftime('%d/%m/%Y')}")
    page1(c, width, height, data)
    c.showPage()
    page2(c, width, height, data)
    c.showPage()
    page3(c, width, height, data)
    c.save()
    return OUT_PDF


def main() -> None:
    DATA_STATUS.mkdir(parents=True, exist_ok=True)
    df = load_maintenances()
    data = analyze(df)
    path = build_pdf(data)
    from_obs_p = sum(1 for p in data.problems if p.source == "observation")
    from_str_p = sum(1 for p in data.problems if p.source == "structured")
    from_obs_a = sum(1 for a in data.actions if a.source == "observation")
    from_str_a = sum(1 for a in data.actions if a.source == "structured")
    print(f"PDF: {path}")
    print(
        f"Manutenções: {data.n_maints} | Reincidências: {data.n_reinc} | "
        f"Câmeras retirada: {data.n_cameras_retirada}"
    )
    print(f"Problemas: {len(data.problems)} (estruturado={from_str_p}, observação={from_obs_p})")
    print(f"Ações: {len(data.actions)} (estruturado={from_str_a}, observação={from_obs_a})")
    print("Buckets problemas (veículos):", data.top_problem_buckets)
    print("Buckets ações (veículos):", data.top_action_buckets)
    print("Top problemas (câmeras):", data.top_problems[:8])
    print("Top ações (câmeras):", data.top_actions[:8])


if __name__ == "__main__":
    main()
