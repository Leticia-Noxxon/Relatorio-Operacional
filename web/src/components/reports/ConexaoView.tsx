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

export function ConexaoView({
  data,
  range,
}: {
  data: ConexaoData;
  range?: { start: string; end: string };
}) {
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
  const collected = (data.coletado_em || "").slice(0, 10);
  const outside =
    Boolean(range && collected && (collected < range.start || collected > range.end));

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
    <div className="flex flex-col gap-2 lg:min-h-0 lg:flex-1">
      <div className="grid shrink-0 grid-cols-2 gap-2 lg:grid-cols-4">
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
        className="lg:flex lg:min-h-0 lg:flex-1 lg:flex-col"
        bodyClassName="flex min-h-0 flex-1 flex-col p-2 lg:overflow-hidden"
        title="Garagens"
        right={
          <div className="flex max-w-full flex-wrap items-center gap-2">
            <div className="inline-flex max-w-full flex-wrap rounded-lg bg-[var(--p4)] p-0.5">
              <ModeButton active={mode === "prefixo"} onClick={() => setMode("prefixo")}>
                Por prefixo (veículo)
              </ModeButton>
              <ModeButton active={mode === "camera"} onClick={() => setMode("camera")}>
                Por câmera
              </ModeButton>
            </div>
            <details className="relative">
              <summary className="cursor-pointer list-none rounded-lg border border-[var(--line)] bg-white px-2.5 py-1 text-xs font-medium text-[var(--p1)]">
                {allSelected
                  ? "Todas as câmeras"
                  : `${selected.length} de ${positions.length} câmeras`}
              </summary>
              <div className="absolute left-0 z-30 mt-1 w-44 rounded-lg border border-[var(--line)] bg-white p-2 shadow-lg sm:left-auto sm:right-0">
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
        {outside ? (
          <p className="px-2 py-6 text-sm text-[var(--muted)]">
            A coleta de {collected.split("-").reverse().join("/")} está fora do período selecionado.
          </p>
        ) : legacy ? (
          <LegacyTable rows={data.all || []} />
        ) : (
          <div className="conexao-scroll min-h-0 w-full max-w-full flex-1 overflow-auto">
            <table className="w-full min-w-[40rem] border-collapse text-[13px]">
              <thead className="sticky top-0 z-10 bg-[var(--p1)] [&_th]:bg-[var(--p1)]">
                <tr className="bg-[var(--p1)] text-white">
                  <th className="px-2 py-1.5 text-left font-semibold">Garagem</th>
                  {mode === "prefixo" ? (
                    <>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Total de veículos</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Veículos com falha</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Veículos 100% offline</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Veículos com erro de SD</th>
                    </>
                  ) : (
                    <>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Total de câmeras</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Câmeras com falha</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Câmeras 100% offline</th>
                      <th className="px-2 py-1.5 text-center font-semibold leading-tight">Câmeras com erro de SD</th>
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
    <div className="max-w-full overflow-x-auto">
    <table className="w-full min-w-[40rem] border-collapse text-[13px]">
      <thead>
        <tr className="bg-[var(--p1)] text-white">
          <th className="px-2 py-1.5 text-left font-semibold">Garagem</th>
          <th className="px-2 py-1.5 text-center font-semibold leading-tight">Total de veículos</th>
          <th className="px-2 py-1.5 text-center font-semibold leading-tight">Veículos com falha</th>
          <th className="px-2 py-1.5 text-center font-semibold leading-tight">Câmeras com falha</th>
          <th className="px-2 py-1.5 text-center font-semibold leading-tight">Câmeras com erro de SD</th>
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
    </div>
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
