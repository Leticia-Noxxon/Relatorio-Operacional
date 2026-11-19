#!/usr/bin/env python3
"""Coleta status-cameras todayOnly e cruza com Jotform (câmera retirada)."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "status_cameras"
JOTFORM = ROOT / "data" / "jotform"
OUT.mkdir(parents=True, exist_ok=True)

AUTH = "https://nxnet-api.noxxonsat.com.br"
API = "https://camera-download-api-dot-noxxonsat-nxnet-spt.rj.r.appspot.com"
EMAIL = os.environ.get("NOXXON_EMAIL", "leticia@noxxonsat.com.br")
PASSWORD = os.environ.get("NOXXON_PASSWORD", "")

REGIAO = {
    692: "Sul",
    660: "Oeste",
    697: "Oeste",
    695: "Oeste",
    698: "Oeste",
    702: "Leste",
    703: "Leste",
    704: "Leste",
    705: "Leste",
    706: "Leste",
    707: "Leste",
    678: "Sul",
    680: "Norte",
    693: "Norte",
    689: "Leste",
    661: "Oeste",
    699: "Oeste",
    696: "Sudeste",
    684: "Sul",
}

SKIP_NAME = re.compile(r"teltex|noxxon|transporte xyz|metropolis\b", re.I)

SLOT_CAM = {
    "Problemas Detectados: Câm. Frontal": 21,
    "Problemas Detectados: Câm. Frente": 22,
    "Problemas Detectados: Câm. Corredor 1": 23,
    "Problemas Detectados: Câm. Corredor 2": 24,
    "Problemas Detectados: Câm. Corredor 3": 25,
    "Problemas Detectados: Câm. Corredor 4": 26,
}
ACT_CAM = {k.replace("Problemas Detectados", "Ações"): v for k, v in SLOT_CAM.items()}


def login() -> str:
    r = requests.post(
        f"{AUTH}/usuarios/login",
        json={"email": EMAIL, "senha": PASSWORD},
        timeout=60,
    )
    if not r.ok:
        print(f"Login NxNet HTTP {r.status_code}", file=sys.stderr)
        raise SystemExit(1)
    token = (r.json() or {}).get("token") or ""
    if not token:
        print("Login NxNet sem token", file=sys.stderr)
        raise SystemExit(1)
    return token


def cam_num(cam: dict) -> int:
    pos = int(cam.get("posicao") or 0)
    if pos >= 1000:
        return 20 + (pos % 100)
    return 20 + pos


def is_offline(cam: dict) -> bool:
    st = (cam.get("status") or "").strip().lower()
    return st == "offline" or (bool(st) and st != "online")


def is_sd_err(cam: dict) -> bool:
    sd = cam.get("sd")
    if sd is None:
        return False
    return str(sd).strip().lower() not in ("ok", "")


def has_tech_problem(cam: dict) -> bool:
    if is_offline(cam):
        return True
    for key in ("sd", "login", "recording"):
        val = cam.get(key)
        if val is None:
            continue
        if str(val).strip().lower() not in ("ok", ""):
            return True
    return False


def load_retirada_pairs() -> set[tuple[int, int]]:
    """(prefixo, câmera) marcados como retirados / sem câmera no Jotform."""
    history_path = JOTFORM / "historico.json"
    frames = []
    if history_path.is_file():
        payload = json.loads(history_path.read_text(encoding="utf-8"))
        records = list((payload.get("records") or {}).values())
        if records:
            frames.append(pd.DataFrame(records))
    files = sorted(p for p in JOTFORM.glob("*.xlsx") if p.is_file())
    frames.extend(pd.read_excel(p) for p in files)
    if not frames:
        return set()
    raw = pd.concat(frames, ignore_index=True)
    if "ID do Envio" in raw.columns:
        raw = raw.sort_values(["ID do Envio"]).drop_duplicates("ID do Envio", keep="last")

    removed: set[tuple[int, int]] = set()
    reinstalled: set[tuple[int, int]] = set()

    for _, row in raw.iterrows():
        try:
            pref = int(float(row.get("Prefixo")))
        except (TypeError, ValueError):
            continue
        for col, cam in SLOT_CAM.items():
            text = str(row.get(col) or "").lower()
            if any(
                k in text
                for k in (
                    "removida por terceiros",
                    "sem câmera",
                    "sem camera",
                    "câmera retirada",
                    "camera retirada",
                )
            ):
                removed.add((pref, cam))
        for col, cam in ACT_CAM.items():
            text = str(row.get(col) or "").lower()
            if "instalação da câmera removida" in text or "instalacao da camera removida" in text:
                reinstalled.add((pref, cam))

        obs = str(row.get("Observações") or "")
        if obs and obs.lower() != "nan":
            # só padrões explícitos de câmera ausente (evita "cartão retirado" / MAC RETIRADA)
            for m in re.finditer(
                r"(?:c[aâ]mera|cam)\s*(2[1-6]).{0,40}(?:retirad\w*\s+por\s+terceiros|removid\w*\s+por\s+terceiros|sem\s+c[aâ]mera)",
                obs,
                re.I,
            ):
                removed.add((pref, int(m.group(1))))
            for m in re.finditer(
                r"(?:retirad\w*|removid\w*)\s+por\s+terceiros.{0,20}(?:c[aâ]mera|cam)\s*(2[1-6])",
                obs,
                re.I,
            ):
                removed.add((pref, int(m.group(1))))

    # se a mesma OS/histórico registrou instalação, não conta como retirada atual
    return removed - reinstalled


def fetch_operadoras(session: requests.Session) -> dict[int, str]:
    path = OUT / "operadoras.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {int(k): str(v).strip() for k, v in raw.items()}
    return {}


def fetch_all_vehicles(session: requests.Session, operadora_id: int) -> list[dict]:
    page = 1
    out: list[dict] = []
    while True:
        r = session.get(
            f"{API}/status-cameras",
            params={
                "operadoraId": str(operadora_id),
                "page": str(page),
                "pageSize": "200",
                "todayOnly": "true",
            },
            timeout=120,
        )
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data") or []
        out.extend(data)
        pag = payload.get("pagination") or {}
        total_pages = int(pag.get("totalPages") or 1)
        if page >= total_pages:
            break
        page += 1
    return out


def summarize_unit(
    nome: str,
    operadora_id: int,
    vehicles: list[dict],
    retirada: set[tuple[int, int]],
) -> dict:
    veiculos_problema = 0
    veiculos_erro_sd = 0
    camera_100_offline = 0
    camera_erro_sd = 0
    camera_21_problema = 0
    camera_retirada = 0
    cameras_problema = 0  # offline/sd/login/rec, excluindo retirada e contando cam21 só na coluna dela

    for v in vehicles:
        try:
            pref = int(str(v.get("prefixo")).strip())
        except (TypeError, ValueError):
            continue
        cams = v.get("cameras") or []
        veic_has_prob = False
        veic_has_sd = False
        for cam in cams:
            cnum = cam_num(cam)
            key = (pref, cnum)
            if key in retirada:
                camera_retirada += 1
                continue
            offline = is_offline(cam)
            sd_err = is_sd_err(cam)
            tech = has_tech_problem(cam)

            if offline:
                camera_100_offline += 1  # inclui câmera 21
            if cnum == 21 and tech:
                camera_21_problema += 1
            if tech:
                cameras_problema += 1
                veic_has_prob = True
            if sd_err:
                camera_erro_sd += 1
                veic_has_sd = True

        if veic_has_prob:
            veiculos_problema += 1
        if veic_has_sd:
            veiculos_erro_sd += 1

    return {
        "operadora_id": operadora_id,
        "unidade": nome,
        "regiao": REGIAO.get(operadora_id, "—"),
        "veiculos_problema": veiculos_problema,
        "veiculos_erro_sd": veiculos_erro_sd,
        "camera_100_offline": camera_100_offline,
        "camera_erro_sd": camera_erro_sd,
        "camera_21_problema": camera_21_problema,
        "camera_retirada": camera_retirada,
        "cameras_problema": cameras_problema,
        "total_veiculos": len(vehicles),
        "metropole": "METRÓPOLE" in nome.upper() or "METROPOLE" in nome.upper(),
    }


def main() -> int:
    if not PASSWORD:
        print("Defina NOXXON_PASSWORD", file=sys.stderr)
        return 2

    retirada = load_retirada_pairs()
    print(f"Pares câmera retirada (Jotform): {len(retirada)}")

    token = login()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    ops = fetch_operadoras(session)
    if not ops:
        # fallback ids conhecidos
        ops = {k: str(k) for k in REGIAO}

    rows = []
    meta = {}
    for oid, nome in sorted(ops.items(), key=lambda x: str(x[1]).casefold()):
        if SKIP_NAME.search(nome or ""):
            continue
        if oid in (0, 3, 681, 709):
            continue
        vehicles = fetch_all_vehicles(session, oid)
        print(f"  {oid} {nome}: {len(vehicles)} veículos")
        row = summarize_unit(nome.strip(), oid, vehicles, retirada)
        rows.append(row)
        meta[str(oid)] = {
            "nome": nome.strip(),
            "n": len(vehicles),
            "sample": vehicles[:1],
        }

    payload = {
        "coletado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": f"{API}/status-cameras?todayOnly=true",
        "retirada_jotform": sorted(
            [{"prefixo": p, "camera": c} for p, c in retirada],
            key=lambda x: (x["prefixo"], x["camera"]),
        ),
        "regras": {
            "camera_100_offline": "offline incluindo câmera 21; exclui câmeras retiradas (Jotform)",
            "camera_21_problema": "câmera 21 com falha técnica, excluindo retirada",
            "camera_erro_sd": "sd != ok, excluindo câmeras retiradas",
            "veiculos_problema": "veículo com ≥1 câmera com falha (excl. retirada)",
            "camera_retirada": "Jotform: removida/sem câmera e sem instalação posterior",
        },
        "rows": rows,
    }
    out = OUT / "conexao_cameras_resumo.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "conexao_cameras_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Salvo", out)
    print(
        "Totais:",
        {
            "veiculos": sum(r["veiculos_problema"] for r in rows),
            "cameras": sum(r["cameras_problema"] for r in rows),
            "retirada": sum(r["camera_retirada"] for r in rows),
            "cam21": sum(r["camera_21_problema"] for r in rows),
            "offline": sum(r["camera_100_offline"] for r in rows),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
