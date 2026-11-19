"use client";

import { useMemo, useState } from "react";
import {
  AngledLabel,
  KpiCard,
  MonthSeg,
  Panel,
  STATUS_COLOR,
} from "@/components/Dashboard";
import { IconBus, IconSd } from "@/components/Icons";

type SdData = {
  period?: { label?: string };
  kpis: {
    prefixes: number;
    total_cards: number;
    ok: number;
    erro: number;
    offline: number;
  };
  months: Array<{
    name: string;
    label: string;
    days: string[];
    rows: Array<{ prefixo: string; camera: number; seq: string[] }>;
  }>;
};

export function SdCardView({ data }: { data: SdData }) {
  const kpis = data.kpis || {
    prefixes: 0,
    total_cards: 0,
    ok: 0,
    erro: 0,
    offline: 0,
  };
  const months = data.months || [];
  const [monthFilter, setMonthFilter] = useState("Todos");

  const visibleMonths = useMemo(() => {
    if (monthFilter === "Todos") return months;
    return months.filter((m) => m.name === monthFilter);
  }, [monthFilter, months]);

  const columns = useMemo(() => {
    const cols: { month: string; day: string; label: string }[] = [];
    for (const m of visibleMonths) {
      for (const d of m.days || []) {
        const [, mo, da] = d.split("-");
        cols.push({
          month: m.name,
          day: d,
          label: da && mo ? `${da}/${mo}` : d,
        });
      }
    }
    return cols;
  }, [visibleMonths]);

  const monthSpans = visibleMonths.map((m) => ({
    name: m.name,
    span: (m.days || []).length,
  }));

  // Unified rows from first available month structure; concat seq across months
  const rows = useMemo(() => {
    const base = months[0]?.rows || [];
    return base.map((r) => {
      const seq: string[] = [];
      for (const m of visibleMonths) {
        const found = (m.rows || []).find(
          (x) => x.prefixo === r.prefixo && x.camera === r.camera,
        );
        if (found) seq.push(...(found.seq || []));
        else seq.push(...Array((m.days || []).length).fill("off"));
      }
      return { prefixo: r.prefixo, camera: r.camera, seq };
    });
  }, [months, visibleMonths]);

  const grouped = useMemo(() => {
    const map = new Map<string, typeof rows>();
    for (const r of rows) {
      const list = map.get(r.prefixo) || [];
      list.push(r);
      map.set(r.prefixo, list);
    }
    return Array.from(map.entries());
  }, [rows]);

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard dense label="Prefixos" value={kpis.prefixes} icon={<IconBus />} />
        <KpiCard
          dense
          label="SD Cards"
          value={kpis.total_cards}
          icon={<IconSd />}
          iconColor="#2F87B5"
        />
        <KpiCard
          dense
          label="Funcionais"
          value={kpis.ok}
          iconTone="#dcfce7"
          iconColor="#16a34a"
          icon={<span className="text-sm font-bold">✓</span>}
        />
        <KpiCard
          dense
          label="Com erro"
          value={kpis.erro}
          iconTone="#fee2e2"
          iconColor="#dc2626"
          icon={<span className="text-sm font-bold">!</span>}
        />
        <KpiCard
          dense
          label="Offline"
          value={kpis.offline}
          iconTone="#f1f5f9"
          iconColor="#64748b"
          icon={<span className="text-sm font-bold">○</span>}
        />
      </div>

      <Panel
        bodyClassName="p-2"
        title="Evolução diária"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#7BC67E]" /> OK
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#E89A9A]" /> Erro
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#C5CED6]" /> Off
            </span>
            <MonthSeg
              months={months.map((m) => m.name)}
              value={monthFilter}
              onChange={setMonthFilter}
            />
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[10px] leading-none">
            <thead>
              <tr>
                <th
                  rowSpan={2}
                  className="sticky left-0 z-10 bg-[var(--p1)] px-2 py-2 text-left text-white"
                >
                  Prefixo
                </th>
                <th
                  rowSpan={2}
                  className="bg-[var(--p1)] px-2 py-2 text-center text-white"
                >
                  Câm
                </th>
                {monthSpans.map((m) => (
                  <th
                    key={m.name}
                    colSpan={m.span || 1}
                    className="bg-[var(--p2)] px-1 py-1.5 text-center text-xs font-bold text-white"
                  >
                    {m.name}
                  </th>
                ))}
              </tr>
              <tr>
                {columns.map((c) => (
                  <th
                    key={`${c.month}-${c.day}`}
                    title={c.day}
                    className="bg-[var(--p1)] px-0 align-bottom"
                  >
                    <AngledLabel text={c.label} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grouped.map(([prefixo, cams]) =>
                cams.map((row, i) => (
                  <tr key={`${prefixo}-${row.camera}`}>
                    {i === 0 ? (
                      <td
                        rowSpan={cams.length}
                        className="sticky left-0 z-10 bg-[#eef6fa] px-1.5 py-px font-bold text-[var(--p1)]"
                      >
                        {prefixo}
                      </td>
                    ) : null}
                    <td className="px-1 py-px text-center">{row.camera}</td>
                    {columns.map((c, ci) => {
                      const st = row.seq[ci] || "off";
                      const color =
                        STATUS_COLOR[st] ||
                        STATUS_COLOR[st === "erro" ? "erro" : "off"];
                      return (
                        <td
                          key={`${prefixo}-${row.camera}-${c.day}`}
                          className="px-px py-px text-center"
                        >
                          <span
                            className="inline-block h-2 w-2 rounded-[1px]"
                            style={{ background: color }}
                            title={`${prefixo}/${row.camera} · ${c.day} · ${st}`}
                          />
                        </td>
                      );
                    })}
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
