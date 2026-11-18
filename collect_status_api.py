#!/usr/bin/env python3
"""Coleta status-cameras/historico (1 dia por vez) via API oficial."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "status_cameras"
OUT.mkdir(parents=True, exist_ok=True)

AUTH = "https://nxnet-api.noxxonsat.com.br"
API = "https://camera-download-api-dot-noxxonsat-nxnet-spt.rj.r.appspot.com"
EMAIL = os.environ.get("NOXXON_EMAIL", "leticia@noxxonsat.com.br")
PASSWORD = os.environ.get("NOXXON_PASSWORD", "")

# prefixo -> data de início no relatório (inclusive)
SB_PREFIXOS: dict[str, date] = {
    "11013": date(2026, 9, 28),
    "11040": date(2026, 9, 28),
    "11048": date(2026, 9, 28),
    "11799": date(2026, 9, 28),
    "11899": date(2026, 9, 28),
    "11082": date(2026, 10, 8),
    "11044": date(2026, 10, 8),
    "11827": date(2026, 10, 8),
    "11961": date(2026, 10, 9),
    "11661": date(2026, 10, 9),
}

JOBS = [
    {
        "key": "metropole_expandir",
        "empresa": "METRÓPOLE - EXPANDIR",
        "operadora_id": 703,
        "prefixos": [str(p) for p in range(32704, 32714)],
        "prefixo_inicio": {str(p): date(2026, 9, 2) for p in range(32704, 32714)},
        "inicio": date(2026, 9, 2),
        "fim": date(2026, 11, 17),
    },
    {
        "key": "santa_brigida",
        "empresa": "SANTA BRÍGIDA",
        "operadora_id": 689,
        "prefixos": list(SB_PREFIXOS.keys()),
        "prefixo_inicio": {k: v for k, v in SB_PREFIXOS.items()},
        "inicio": date(2026, 9, 28),
        "fim": date(2026, 11, 17),
    },
]


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def login() -> str:
    r = requests.post(
        f"{AUTH}/usuarios/login",
        json={"email": EMAIL, "senha": PASSWORD},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def fetch_day(session: requests.Session, operadora_id: int, day: date) -> dict:
    params = {
        "operadoraId": str(operadora_id),
        "dataInicio": day.isoformat(),
        "dataFim": day.isoformat(),
        "pageSize": "1000",
    }
    r = session.get(f"{API}/status-cameras/historico", params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def cam_num(cam: dict) -> int:
    return 20 + int(cam.get("posicao") or 0)


def slim_camera(cam: dict) -> dict:
    return {
        "nome": cam.get("nome"),
        "posicao": cam.get("posicao"),
        "camera": cam_num(cam),
        "dias_ok": int(cam.get("dias_ok") or 0),
        "dias_com_falha": int(cam.get("dias_com_falha") or 0),
        "dias_offline": int(cam.get("dias_offline") or 0),
        "dias_sd_erro": int(cam.get("dias_sd_erro") or 0),
        "dias_gravacao_erro": int(cam.get("dias_gravacao_erro") or 0),
        "dias_login_erro": int(cam.get("dias_login_erro") or 0),
        "dias_sem_dado": int(cam.get("dias_sem_dado") or 0),
        "online_percent": cam.get("online_percent"),
    }


def main() -> int:
    if not PASSWORD:
        print("Defina NOXXON_PASSWORD", file=sys.stderr)
        return 2

    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    token = login()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    for job in JOBS:
        if only and job["key"] not in only:
            continue
        print(f"=== {job['empresa']} {job['inicio']}..{job['fim']} ===")
        result = {
            "empresa": job["empresa"],
            "operadora_id": job["operadora_id"],
            "prefixos_alvo": job["prefixos"],
            "prefixo_inicio": {
                p: job["prefixo_inicio"][p].isoformat() for p in job["prefixos"]
            },
            "periodo": {"inicio": job["inicio"].isoformat(), "fim": job["fim"].isoformat()},
            "coletado_em": datetime.now().isoformat(timespec="seconds"),
            "fonte": f"{API}/status-cameras/historico",
            "regra_cor": "verde se dias_offline==0; vermelho se offline; cinza fora do início do prefixo",
            "dias": {},
        }
        for day in daterange(job["inicio"], job["fim"]):
            raw = fetch_day(session, job["operadora_id"], day)
            by_pref = {str(v.get("prefixo")): v for v in raw.get("data") or []}
            day_out = {"prefixos": {}, "periodo_api": raw.get("periodo")}
            for pref in job["prefixos"]:
                start = job["prefixo_inicio"][pref]
                if day < start:
                    day_out["prefixos"][pref] = {
                        "status": "fora_periodo",
                        "cameras": {},
                        "inicio_prefixo": start.isoformat(),
                    }
                    continue
                v = by_pref.get(pref)
                if not v:
                    day_out["prefixos"][pref] = {"status": "ausente", "cameras": {}}
                    continue
                cams = {}
                for c in v.get("cameras") or []:
                    sc = slim_camera(c)
                    cams[str(sc["camera"])] = sc
                day_out["prefixos"][pref] = {
                    "status": "ok",
                    "id_veiculo": v.get("id_veiculo"),
                    "placa": v.get("placa"),
                    "numero_serial": v.get("numero_serial"),
                    "cameras": cams,
                }
            result["dias"][day.isoformat()] = day_out
            n_ok = sum(1 for p in job["prefixos"] if day_out["prefixos"][p]["status"] == "ok")
            n_scope = sum(
                1 for p in job["prefixos"] if day >= job["prefixo_inicio"][p]
            )
            print(f"  {day.isoformat()}: {n_ok}/{n_scope} prefixos no escopo")

        out = OUT / f"{job['key']}_{job['inicio'].isoformat()}_a_{job['fim'].isoformat()}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Salvo", out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
