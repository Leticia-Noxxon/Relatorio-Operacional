"use client";

import { useMemo, useState } from "react";
import {
  Doughnut,
  InlineQtyBar,
  KpiCard,
  Panel,
  VerticalBars,
} from "@/components/Dashboard";
import {
  IconCamera,
  IconRepeat,
  IconServer,
  IconWarehouse,
  IconWrench,
} from "@/components/Icons";

type ExecRecord = {
  date: string;
  garagem: string;
  prefixo: string;
  problems?: string[];
  actions?: string[];
  problem_buckets?: string[];
};

type ExecData = {
  period?: { label?: string; start?: string; end?: string };
  legacy_period_end?: string;
  legacy_maintenances?: number;
  records?: ExecRecord[];
  kpis: {
    maintenances: number;
    reincidences: number;
    prefixes: number;
    garages: number;
    cameras_removed: number;
  };
  problem_buckets: [string, number][];
  top_problems: [string, number][];
  top_actions: [string, number][];
  garages: {
    name: string;
    maints: number;
    reinc: number;
    prefixes?: number;
    top_problems?: [string, number][];
    top_actions?: [string, number][];
  }[];
  garage_bucket_problems: {
    name: string;
    buckets: [string, number][];
  }[];
};

export function ExecutivoView({
  data,
  range,
}: {
  data: ExecData;
  range?: { start: string; end: string };
}) {
  const sliced = useMemo(() => sliceExecutivo(data, range), [data, range]);
  const problemBuckets = sliced.problemBuckets;
  const topProblems = sliced.topProblems;
  const topActions = sliced.topActions;
  const garages = sliced.garages;
  const occ = sliced.occ;
  const kpis = sliced.kpis;
  const note = sliced.note;
  const [garageFilter, setGarageFilter] = useState<string | null>(null);
  const selected = garages.find((g) => g.name === garageFilter) || null;
  const selectedOcc = occ.find((g) => g.name === garageFilter) || null;

  function toggleGarage(name: string) {
    setGarageFilter((current) => (current === name ? null : name));
  }

  const viewKpis = selected
    ? {
        maintenances: selected.maints,
        reincidences: selected.reinc,
        prefixes: selected.prefixes ?? 0,
        garages: 1,
        cameras_removed: null as number | null,
      }
    : { ...kpis, cameras_removed: kpis.cameras_removed as number | null };
  const viewGarages = selected ? [selected] : garages;
  const viewOcc = selectedOcc ? [selectedOcc] : occ;
  const viewBuckets = selectedOcc
    ? selectedOcc.buckets || []
    : problemBuckets;
  const switchN =
    viewBuckets.find(([k]) => k.toLowerCase().includes("switch"))?.[1] || 0;
  const viewProblems = selected?.top_problems?.length
    ? selected.top_problems
    : selectedOcc
      ? viewBuckets
      : topProblems;
  const viewActions = selected ? selected.top_actions || [] : topActions;
  const maxP = Math.max(...viewProblems.map(([, v]) => v), 1);
  const maxA = Math.max(...viewActions.map(([, v]) => v), 1);

  return (
    <div className="space-y-3">
      {note ? (
        <p className="rounded-lg bg-[#fff7ed] px-3 py-2 text-sm text-[#9a3412]">{note}</p>
      ) : null}
      {selected ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-[#135487] px-3 py-2 text-sm font-semibold text-white">
          <span>Filtro: {selected.name}</span>
          <button
            type="button"
            onClick={() => setGarageFilter(null)}
            className="rounded-md bg-white/15 px-2 py-0.5 text-xs"
          >
            Limpar
          </button>
          <span className="text-xs font-normal text-white/80">
            Clique de novo na garagem para ver todas.
          </span>
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Manutenções"
          value={fmt(viewKpis.maintenances)}
          icon={<IconWrench />}
        />
        <KpiCard
          label="Reincidências"
          value={fmt(viewKpis.reincidences)}
          icon={<IconRepeat />}
          iconColor="#2F87B5"
        />
        <KpiCard
          label="Prefixos"
          value={fmt(viewKpis.prefixes)}
          icon={<IconServer />}
          iconColor="#47BCDF"
        />
        <KpiCard
          label="Garagens"
          value={fmt(viewKpis.garages)}
          icon={<IconWarehouse />}
          iconColor="#2F87B5"
        />
        <KpiCard
          label="Câmeras retirada"
          value={
            viewKpis.cameras_removed == null ? "—" : fmt(viewKpis.cameras_removed)
          }
          icon={<IconCamera />}
          iconTone="#fee2e2"
          iconColor="#dc2626"
        />
      </div>

      <Panel title="Indicadores por garagem">
        <div className="overflow-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-left">Garagem</th>
                <th className="px-3 py-2 text-center">Manutenções</th>
                <th className="px-3 py-2 text-center">Prefixos</th>
                <th className="px-3 py-2 text-center">Reincidências</th>
                <th className="px-3 py-2 text-center">% reincidências</th>
              </tr>
            </thead>
            <tbody>
              {viewGarages.map((g, i) => {
                const pct = g.maints ? (g.reinc / g.maints) * 100 : 0;
                const bad = pct > 20;
                const active = garageFilter === g.name;
                return (
                  <tr
                    key={g.name}
                    className={active ? "bg-[#d7eef8]" : i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                  >
                    <td className="px-3 py-2 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleGarage(g.name)}
                        aria-pressed={active}
                        className="text-left underline-offset-2 hover:underline"
                      >
                        {g.name}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-center">{fmt(g.maints)}</td>
                    <td className="px-3 py-2 text-center">
                      {fmt(g.prefixes ?? 0)}
                    </td>
                    <td className="px-3 py-2 text-center">{fmt(g.reinc)}</td>
                    <td
                      className={`px-3 py-2 text-center font-normal ${
                        bad ? "text-[var(--danger)]" : "text-[#15803d]"
                      }`}
                    >
                      {pct.toFixed(1).replace(".", ",")}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-[1.2fr_0.9fr]">
        <Panel title="Problemas por categoria">
          <VerticalBars
            items={viewBuckets.map(([label, value]) => ({ label, value }))}
          />
        </Panel>
        <Panel title="Disponibilidade">
          <div className="flex h-full min-h-[280px] items-center justify-center gap-16 py-6">
            <Doughnut
              online={Math.max(viewKpis.maintenances - switchN, 0)}
              offline={switchN}
              size={250}
            />
            <div className="space-y-6 text-base text-[var(--muted)]">
              <div className="inline-flex items-center gap-2">
                <i className="inline-block h-3 w-3 rounded-sm bg-[#7BC67E]" />{" "}
                Online
              </div>
              <div className="inline-flex items-center gap-2">
                <i className="inline-block h-3 w-3 rounded-sm bg-[#E89A9A]" />{" "}
                Offline
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Panel title="Problemas mais identificados (Câmera)">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-left">Problema</th>
                <th className="w-[42%] px-3 py-2 text-center">Qtde</th>
              </tr>
            </thead>
            <tbody>
              {viewProblems.map(([label, value], i) => (
                <tr
                  key={label}
                  className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                >
                  <td className="px-3 py-2">{label}</td>
                  <td className="px-3 py-2">
                    <InlineQtyBar value={value} max={maxP} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Ações mais realizadas (Câmera)">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-left">Ação</th>
                <th className="w-[42%] px-3 py-2 text-center">Qtde</th>
              </tr>
            </thead>
            <tbody>
              {viewActions.length === 0 ? (
                <tr>
                  <td className="px-3 py-3 text-[var(--muted)]" colSpan={2}>
                    Sem detalhamento de ações para esta garagem.
                  </td>
                </tr>
              ) : null}
              {viewActions.map(([label, value], i) => (
                <tr
                  key={label}
                  className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                >
                  <td className="px-3 py-2">{label}</td>
                  <td className="px-3 py-2">
                    <InlineQtyBar value={value} max={maxA} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <Panel title="Resumo de ocorrências por garagem">
        <div className="overflow-auto">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-left">Garagem</th>
                <th className="px-3 py-2 text-center">Cabeamento</th>
                <th className="px-3 py-2 text-center">Switch</th>
                <th className="px-3 py-2 text-center">Câmera</th>
                <th className="px-3 py-2 text-center">Cartão de memória</th>
                <th className="px-3 py-2 text-center">Total</th>
              </tr>
            </thead>
            <tbody>
              {viewOcc.map((g, i) => {
                const b = Object.fromEntries(g.buckets || []);
                const cab = Number(b["Cabeamento"] || 0);
                const sw = Number(b["Switch"] || 0);
                const cam = Number(b["Câmera"] || 0);
                const mem = Number(b["Cartão de Memória"] || 0);
                return (
                  <tr
                    key={g.name}
                    className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                  >
                    <td className="px-3 py-2 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleGarage(g.name)}
                        className="text-left underline-offset-2 hover:underline"
                      >
                        {g.name}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-center">{cab}</td>
                    <td className="px-3 py-2 text-center">{sw}</td>
                    <td className="px-3 py-2 text-center">{cam}</td>
                    <td className="px-3 py-2 text-center">{mem}</td>
                    <td className="px-3 py-2 text-center font-bold">
                      {cab + sw + cam + mem}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function fmt(n: number) {
  return n.toLocaleString("pt-BR");
}

function sliceExecutivo(data: ExecData, range?: { start: string; end: string }) {
  const base = {
    kpis: data.kpis || {
      maintenances: 0,
      reincidences: 0,
      prefixes: 0,
      garages: 0,
      cameras_removed: 0,
    },
    problemBuckets: data.problem_buckets || [],
    topProblems: data.top_problems || [],
    topActions: data.top_actions || [],
    garages: data.garages || [],
    occ: data.garage_bucket_problems || [],
    note: "",
  };
  const start = data.period?.start;
  const end = data.period?.end;
  if (!range || !start || !end || (range.start <= start && range.end >= end)) return base;
  const records = (data.records || []).filter(
    (row) => row.date >= range.start && row.date <= range.end,
  );
  const byGarage = new Map<string, { maints: number; prefixes: Set<string> }>();
  const problems = new Map<string, number>();
  const actions = new Map<string, number>();
  const problemBuckets = new Map<string, number>();
  const garageProblems = new Map<string, Map<string, number>>();
  const garageActions = new Map<string, Map<string, number>>();
  const garageBuckets = new Map<string, Map<string, number>>();
  for (const row of records) {
    const garage = byGarage.get(row.garagem) || { maints: 0, prefixes: new Set<string>() };
    garage.maints += 1;
    if (row.prefixo) garage.prefixes.add(row.prefixo);
    byGarage.set(row.garagem, garage);
    const gp = garageProblems.get(row.garagem) || new Map<string, number>();
    const ga = garageActions.get(row.garagem) || new Map<string, number>();
    const gb = garageBuckets.get(row.garagem) || new Map<string, number>();
    (row.problems || []).forEach((label, index) => {
      problems.set(label, (problems.get(label) || 0) + 1);
      gp.set(label, (gp.get(label) || 0) + 1);
      const bucket = row.problem_buckets?.[index] || "Câmera";
      problemBuckets.set(bucket, (problemBuckets.get(bucket) || 0) + 1);
      gb.set(bucket, (gb.get(bucket) || 0) + 1);
    });
    (row.actions || []).forEach((label) => {
      actions.set(label, (actions.get(label) || 0) + 1);
      ga.set(label, (ga.get(label) || 0) + 1);
    });
    garageProblems.set(row.garagem, gp);
    garageActions.set(row.garagem, ga);
    garageBuckets.set(row.garagem, gb);
  }
  const garages = [...byGarage.entries()]
    .map(([name, info]) => ({
      name,
      maints: info.maints,
      reinc: 0,
      prefixes: info.prefixes.size,
      top_problems: [...(garageProblems.get(name) || [])].sort((a, b) => b[1] - a[1]).slice(0, 12) as [string, number][],
      top_actions: [...(garageActions.get(name) || [])].sort((a, b) => b[1] - a[1]).slice(0, 12) as [string, number][],
    }))
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const topProblems = [...problems.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  const topActions = [...actions.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  return {
    kpis: {
      maintenances: records.length,
      reincidences: 0,
      prefixes: new Set(records.map((row) => row.prefixo).filter(Boolean)).size,
      garages: garages.length,
      cameras_removed: 0,
    },
    problemBuckets: [...problemBuckets.entries()].sort((a, b) => b[1] - a[1]) as [string, number][],
    topProblems,
    topActions,
    garages,
    occ: garages.map((garage) => ({
      name: garage.name,
      buckets: [...(garageBuckets.get(garage.name) || [])].sort((a, b) => b[1] - a[1]) as [string, number][],
    })),
    note: `Período filtrado: ${records.length} manutenções entre ${range.start.split("-").reverse().join("/")} e ${range.end.split("-").reverse().join("/")}.`,
  };
}
