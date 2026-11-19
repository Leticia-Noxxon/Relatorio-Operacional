"use client";

import { useMemo, useState } from "react";
import { KpiCard, Panel } from "@/components/Dashboard";
import { IconBus, IconCamera, IconSd } from "@/components/Icons";

type CamFlag = { pos: number; off?: number; sd?: number; falha?: number };

type Vehicle = {
  garagem: string;
  prefixo?: string;
  cameras: CamFlag[];
};

type LegacyRow = {
  unidade: string;
  veiculos_problema: number;
  camera_100_offline: number;
  camera_erro_sd: number;
  cameras_problema: number;
  veiculos_erro_sd?: number;
  total_veiculos?: number;
};

type ConexaoData = {
  coletado_em?: string;
  posicoes?: number[];
  veiculos?: Vehicle[];
  totais?: {
    veiculos_problema: number;
    cameras_problema: number;
    veiculos_erro_sd?: number;
    cameras_erro_sd?: number;
    unidades: number;
  };
  all?: LegacyRow[];
};

type Agg = {
  garagem: string;
  veiculos: number;
  veiculos_falha: number;
  veiculos_offline: number;
  veiculos_sd: number;
  cameras: number;
  cameras_falha: number;
  cameras_offline: number;
  cameras_sd: number;
};

export function ConexaoView({ data }: { data: ConexaoData }) {
  const vehicles = data.veiculos || [];
  const positions = useMemo(() => {
    const fromData = data.posicoes || [];
    if (fromData.length) return [...fromData].sort((a, b) => a - b);
    const set = new Set<number>();
    for (const v of vehicles) {
      for (const c of v.cameras || []) set.add(c.pos);
    }
    return set.size ? [...set].sort((a, b) => a - b) : [21, 22, 23, 24, 25, 26];
  }, [data.posicoes, vehicles]);
  const [mode, setMode] = useState<"prefixo" | "camera">("prefixo");
  const [picked, setPicked] = useState<number[] | null>(null);
  const selected = picked ?? positions;
  const allSelected = selected.length === positions.length;

  function togglePos(pos: number) {
    setPicked((current) => {
      const base = current ?? [...positions];
      return base.includes(pos) ? base.filter((p) => p !== pos) : [...base, pos].sort((a, b) => a - b);
    });
  }

  const rows = useMemo(() => aggregate(vehicles, selected), [vehicles, selected]);
  const legacy = !vehicles.length;

  const sums = rows.reduce(
    (acc, row) => {
      acc.veiculos += row.veiculos;
      acc.veiculos_falha += row.veiculos_falha;
      acc.veiculos_offline += row.veiculos_offline;
      acc.veiculos_sd += row.veiculos_sd;
      acc.cameras += row.cameras;
      acc.cameras_falha += row.cameras_falha;
      acc.cameras_offline += row.cameras_offline;
      acc.cameras_sd += row.cameras_sd;
      return acc;
    },
    {
      veiculos: 0,
      veiculos_falha: 0,
      veiculos_offline: 0,
      veiculos_sd: 0,
      cameras: 0,
      cameras_falha: 0,
      cameras_offline: 0,
      cameras_sd: 0,
    },
  );

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          dense
          label="Veículos com falha"
          value={fmt(legacy ? data.totais?.veiculos_problema || 0 : sums.veiculos_falha)}
          icon={<IconBus />}
        />
        <KpiCard
          dense
          label="Câmeras com falha"
          value={fmt(legacy ? data.totais?.cameras_problema || 0 : sums.cameras_falha)}
          icon={<IconCamera />}
          iconTone="#fee2e2"
          iconColor="#dc2626"
        />
        <KpiCard
          dense
          label="Veículos com erro de SD"
          value={fmt(legacy ? data.totais?.veiculos_erro_sd || 0 : sums.veiculos_sd)}
          icon={<IconSd />}
          iconColor="#2F87B5"
        />
        <KpiCard
          dense
          label="Câmeras com erro de SD"
          value={fmt(legacy ? data.totais?.cameras_erro_sd || 0 : sums.cameras_sd)}
          icon={<span className="text-sm font-bold">!</span>}
          iconTone="#fff7ed"
          iconColor="#ea580c"
        />
      </div>

      <Panel
        bodyClassName="p-2"
        title="Garagens"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg bg-[var(--p4)] p-0.5">
              <ModeButton active={mode === "prefixo"} onClick={() => setMode("prefixo")}>
                Por prefixo (veículo)
              </ModeButton>
              <ModeButton active={mode === "camera"} onClick={() => setMode("camera")}>
                Por câmera
              </ModeButton>
            </div>
            <details className="relative">
              <summary className="cursor-pointer list-none rounded-lg border border-[var(--line)] bg-white px-2.5 py-1 text-xs font-semibold text-[var(--p1)]">
                {allSelected ? "Todas as câmeras" : `Câmeras: ${selected.join(", ")}`}
              </summary>
              <div className="absolute right-0 z-20 mt-1 w-44 rounded-lg border border-[var(--line)] bg-white p-2 shadow-lg">
                {positions.map((pos) => (
                  <label key={pos} className="flex items-center gap-2 py-0.5 text-xs">
                    <input
                      type="checkbox"
                      checked={selected.includes(pos)}
                      onChange={() => togglePos(pos)}
                    />
                    Câmera {pos}
                  </label>
                ))}
                <button
                  type="button"
                  className="mt-1 text-xs font-semibold text-[var(--p1)]"
                  onClick={() => setPicked(null)}
                >
                  Marcar todas
                </button>
              </div>
            </details>
          </div>
        }
      >
        {legacy ? (
          <LegacyTable rows={data.all || []} />
        ) : (
          <div>
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-[var(--p1)] text-white">
                  <th className="px-2 py-1 text-left">Garagem</th>
                  {mode === "prefixo" ? (
                    <>
                      <th className="px-2 py-1 text-center">Total de veículos</th>
                      <th className="px-2 py-1 text-center">Veíc. com falha</th>
                      <th className="px-2 py-1 text-center">Veíc. 100% offline</th>
                      <th className="px-2 py-1 text-center">Veíc. erro SD</th>
                    </>
                  ) : (
                    <>
                      <th className="px-2 py-1 text-center">Total de câmeras</th>
                      <th className="px-2 py-1 text-center">Câmeras com falha</th>
                      <th className="px-2 py-1 text-center">Câmeras 100% offline</th>
                      <th className="px-2 py-1 text-center">Câmeras com erro de SD</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={row.garagem} className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}>
                    <td className="px-2 py-0.5 font-medium">{row.garagem}</td>
                    {mode === "prefixo" ? (
                      <>
                        <td className="px-2 py-0.5 text-center">{fmt(row.veiculos)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.veiculos_falha)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.veiculos_offline)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.veiculos_sd)}</td>
                      </>
                    ) : (
                      <>
                        <td className="px-2 py-0.5 text-center">{fmt(row.cameras)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.cameras_falha)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.cameras_offline)}</td>
                        <td className="px-2 py-0.5 text-center">{fmt(row.cameras_sd)}</td>
                      </>
                    )}
                  </tr>
                ))}
                <tr className="bg-[var(--p4)] font-bold">
                  <td className="px-2 py-1">Total</td>
                  {mode === "prefixo" ? (
                    <>
                      <td className="px-2 py-1 text-center">{fmt(sums.veiculos)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.veiculos_falha)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.veiculos_offline)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.veiculos_sd)}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-2 py-1 text-center">{fmt(sums.cameras)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.cameras_falha)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.cameras_offline)}</td>
                      <td className="px-2 py-1 text-center">{fmt(sums.cameras_sd)}</td>
                    </>
                  )}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`h-7 rounded-md px-2.5 text-xs font-semibold ${
        active ? "bg-[var(--p1)] text-white" : "text-[var(--p1)]"
      }`}
    >
      {children}
    </button>
  );
}

function LegacyTable({ rows }: { rows: LegacyRow[] }) {
  return (
    <table className="w-full border-collapse text-xs">
      <thead>
        <tr className="bg-[var(--p1)] text-white">
          <th className="px-2 py-1 text-left">Garagem</th>
          <th className="px-2 py-1 text-center">Total de veículos</th>
          <th className="px-2 py-1 text-center">Veíc. com falha</th>
          <th className="px-2 py-1 text-center">Câmeras com falha</th>
          <th className="px-2 py-1 text-center">Câmeras com erro de SD</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.unidade}>
            <td className="px-2 py-0.5">{row.unidade}</td>
            <td className="px-2 py-0.5 text-center">{fmt(row.total_veiculos || 0)}</td>
            <td className="px-2 py-0.5 text-center">{fmt(row.veiculos_problema)}</td>
            <td className="px-2 py-0.5 text-center">{fmt(row.cameras_problema)}</td>
            <td className="px-2 py-0.5 text-center">{fmt(row.camera_erro_sd)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function aggregate(vehicles: Vehicle[], positions: number[]): Agg[] {
  const allowed = new Set(positions);
  const map = new Map<string, Agg>();
  for (const vehicle of vehicles) {
    const cams = (vehicle.cameras || []).filter((c) => allowed.has(c.pos));
    if (!cams.length) continue;
    const row = map.get(vehicle.garagem) || {
      garagem: vehicle.garagem,
      veiculos: 0,
      veiculos_falha: 0,
      veiculos_offline: 0,
      veiculos_sd: 0,
      cameras: 0,
      cameras_falha: 0,
      cameras_offline: 0,
      cameras_sd: 0,
    };
    row.veiculos += 1;
    if (cams.some((c) => c.falha)) row.veiculos_falha += 1;
    if (cams.every((c) => c.off)) row.veiculos_offline += 1;
    if (cams.some((c) => c.sd)) row.veiculos_sd += 1;
    row.cameras += cams.length;
    row.cameras_falha += cams.filter((c) => c.falha).length;
    row.cameras_offline += cams.filter((c) => c.off).length;
    row.cameras_sd += cams.filter((c) => c.sd).length;
    map.set(vehicle.garagem, row);
  }
  return [...map.values()].sort((a, b) => b.veiculos_falha - a.veiculos_falha || a.garagem.localeCompare(b.garagem, "pt-BR"));
}

function fmt(n: number) {
  return (n || 0).toLocaleString("pt-BR");
}
