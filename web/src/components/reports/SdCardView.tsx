"use client";

import { useMemo, useState } from "react";
import {
  AngledLabel,
  KpiCard,
  MonthSeg,
  Panel,
  STATUS_COLOR,
  WheelPan,
} from "@/components/Dashboard";
import { IconBus, IconSd } from "@/components/Icons";

type SdData = {
  period?: { label?: string; start?: string; end?: string };
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

export function SdCardView({
  data,
  range,
}: {
  data: SdData;
  range?: { start: string; end: string };
}) {
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
    const year = (data.period?.start || "2026-01-01").slice(0, 4);
    const cols: { month: string; day: string; label: string; iso: string }[] = [];
    for (const m of visibleMonths) {
      (m.days || []).forEach((d, index) => {
        const iso = toIso(d, year);
        if (range && iso && (iso < range.start || iso > range.end)) return;
        cols.push({
          month: m.name,
          day: d,
          label: d.includes("-") ? d.slice(5) : d,
          iso,
          index,
          monthName: m.name,
        } as { month: string; day: string; label: string; iso: string });
      });
    }
    return cols;
  }, [visibleMonths, data.period?.start, range]);

  const monthSpans = useMemo(() => {
    const spans: { name: string; span: number }[] = [];
    for (const col of columns) {
      const last = spans[spans.length - 1];
      if (last && last.name === col.month) last.span += 1;
      else spans.push({ name: col.month, span: 1 });
    }
    return spans;
  }, [columns]);

  const rows = useMemo(() => {
    const base = months[0]?.rows || [];
    return base.map((r) => {
      const seq: string[] = [];
      for (const col of columns) {
        const month = visibleMonths.find((m) => m.name === col.month);
        const found = (month?.rows || []).find(
          (x) => x.prefixo === r.prefixo && x.camera === r.camera,
        );
        const dayIndex = (month?.days || []).indexOf(col.day);
        seq.push(found?.seq?.[dayIndex] || "off");
      }
      return { prefixo: r.prefixo, camera: r.camera, seq };
    });
  }, [months, visibleMonths, columns]);

function toIso(label: string, year: string) {
  const parts = label.split("/");
  if (parts.length >= 2 && parts[0] && parts[1]) {
    const y = parts[2] || year;
    return `${y}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
  }
  return /^\d{4}-\d{2}-\d{2}/.test(label) ? label.slice(0, 10) : "";
}

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
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard dense label="Prefixos" value={kpis.prefixes} icon={<IconBus />} />
        <KpiCard
          dense
          label="Cartões SD"
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
          <div className="flex max-w-full flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] font-normal text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#7BC67E]" /> Sem falha
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] font-normal text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#E89A9A]" /> Com erro
            </span>
            <span className="inline-flex items-center gap-1 text-[11px] font-normal text-[var(--muted)]">
              <i className="inline-block h-2 w-2 rounded-sm bg-[#C5CED6]" /> Offline
            </span>
            <MonthSeg
              months={months.map((m) => m.name)}
              value={monthFilter}
              onChange={setMonthFilter}
            />
          </div>
        }
      >
        <WheelPan className="max-h-[min(720px,calc(100dvh-15rem))] min-h-[240px]">
          <table className="w-max min-w-full border-collapse text-[13px]">
            <thead className="sticky top-0 z-20">
              <tr>
                <th
                  rowSpan={2}
                  className="sticky left-0 z-30 bg-[var(--p1)] px-2 py-2 text-left text-white"
                >
                  Prefixo
                </th>
                <th
                  rowSpan={2}
                  className="bg-[var(--p1)] px-2 py-2 text-center text-white"
                >
                  Câmera
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
                    className="w-[16px] min-w-[16px] bg-[var(--p1)] px-0 py-1 align-bottom"
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
                        className="sticky left-0 z-10 bg-[#eef6fa] px-2 py-1 font-bold text-[var(--p1)]"
                      >
                        {prefixo}
                      </td>
                    ) : null}
                    <td className="px-2 py-1 text-center">{row.camera}</td>
                    {columns.map((c, ci) => {
                      const st = row.seq[ci] || "off";
                      const color =
                        STATUS_COLOR[st] ||
                        STATUS_COLOR[st === "erro" ? "erro" : "off"];
                      return (
                        <td
                          key={`${prefixo}-${row.camera}-${c.day}`}
                          className="px-0.5 py-1 text-center"
                        >
                          <span
                            className="inline-block h-3.5 w-3.5 rounded-[2px]"
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
        </WheelPan>
      </Panel>
    </div>
  );
}
