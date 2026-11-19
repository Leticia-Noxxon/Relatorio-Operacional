"use client";

import { useMemo, useState } from "react";
import {
  AngledLabel,
  Doughnut,
  MonthSeg,
  Panel,
  STATUS_COLOR,
  TableFrame,
  formatPercent,
} from "@/components/Dashboard";

type SantaData = {
  period?: { label?: string; start?: string; end?: string };
  prefixes: string[];
  stats: Record<
    string,
    { ok: number; bad: number; total: number; pct_ok?: number; pct_bad?: number }
  >;
  months: Array<{
    name: string;
    label: string;
    ok: number;
    bad: number;
    days: string[];
    grid: Array<{ day: string; label?: string; cells: string[] }>;
  }>;
};

export function SantaView({
  data,
  range,
}: {
  data: SantaData;
  range?: { start: string; end: string };
}) {
  const prefixes = data.prefixes || [];
  const months = data.months || [];
  const stats = data.stats || {};
  const [monthFilter, setMonthFilter] = useState("Todos");

  const visibleMonths = useMemo(() => {
    if (monthFilter === "Todos") return months;
    return months.filter((m) => m.name === monthFilter);
  }, [monthFilter, months]);

  const columns = useMemo(() => {
    const year = (data.period?.start || "2026-01-01").slice(0, 4);
    const cols: { month: string; day: string; label: string }[] = [];
    for (const m of visibleMonths) {
      for (const d of m.days || []) {
        const iso = dayIso(d, year);
        if (range && iso && (iso < range.start || iso > range.end)) continue;
        const [da, mo] = d.split("/");
        cols.push({
          month: m.name,
          day: d,
          label: da && mo ? `${da}/${mo}` : d,
        });
      }
    }
    return cols;
  }, [visibleMonths, data.period?.start, range]);

  const statusAt = (prefixIdx: number, day: string) => {
    for (const m of visibleMonths) {
      const g = (m.grid || []).find((x) => x.day === day);
      if (g) return g.cells[prefixIdx] || "na";
    }
    return "na";
  };

  const monthSpans = useMemo(() => {
    const spans: { name: string; span: number }[] = [];
    for (const col of columns) {
      const last = spans[spans.length - 1];
      if (last && last.name === col.month) last.span += 1;
      else spans.push({ name: col.month, span: 1 });
    }
    return spans;
  }, [columns]);

  const shownStats = useMemo(() => {
    const out: SantaData["stats"] = {};
    prefixes.forEach((p, pi) => {
      let ok = 0;
      let bad = 0;
      for (const col of columns) {
        const st = statusAt(pi, col.day);
        if (st === "ok") ok += 1;
        else if (st === "bad") bad += 1;
      }
      out[p] = { ok, bad, total: ok + bad };
    });
    return out;
  }, [prefixes, columns, visibleMonths]);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <Panel title="Resumo por prefixo">
          <TableFrame>
            <table className="w-full border-collapse text-[13px] sm:text-sm">
              <thead>
                <tr className="bg-[var(--p1)] text-white">
                  <th className="px-3 py-2 text-left">Prefixo</th>
                  <th className="px-3 py-2 text-center">Total de registros</th>
                  <th className="px-3 py-2 text-center">Registros sem falha</th>
                  <th className="px-3 py-2 text-center">Registros com falha</th>
                </tr>
              </thead>
              <tbody>
                {prefixes.map((p, i) => {
                  const s = shownStats[p] || stats[p] || { total: 0, ok: 0, bad: 0 };
                  return (
                    <tr
                      key={p}
                      className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                    >
                      <td className="px-3 py-2 font-bold text-[var(--p1)]">
                        {p}
                      </td>
                      <td className="px-3 py-2 text-center font-normal">{s.total}</td>
                      <td className="px-3 py-2 text-center font-normal text-[#15803d]">
                        {s.ok}
                      </td>
                      <td className="px-3 py-2 text-center font-normal text-[var(--danger)]">
                        {s.bad}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableFrame>
        </Panel>

        <Panel title="Disponibilidade por mês">
          <div className="grid w-full grid-cols-1 items-start justify-items-center gap-8 py-2 min-[720px]:grid-cols-3 min-[720px]:gap-4">
            {months.map((m) => {
              const total = m.ok + m.bad;
              return (
                <div key={m.name} className="flex w-full max-w-[200px] flex-col items-center">
                  <Doughnut
                    online={m.ok}
                    offline={m.bad}
                    label={m.name}
                    size={176}
                  />
                  <p className="mt-2 text-center text-[11px] font-normal leading-relaxed text-[var(--muted)]">
                    <span className="inline-flex items-center gap-1">
                      <i className="inline-block h-2 w-2 rounded-sm bg-[#7BC67E]" />
                      {formatPercent(m.ok, total)} online
                    </span>
                    <span className="mx-1 text-[var(--line)]">·</span>
                    <span className="inline-flex items-center gap-1">
                      <i className="inline-block h-2 w-2 rounded-sm bg-[#E89A9A]" />
                      {formatPercent(m.bad, total)} offline
                    </span>
                  </p>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      <Panel
        title="Calendário / Evolução"
        right={
          <MonthSeg
            months={months.map((m) => m.name)}
            value={monthFilter}
            onChange={setMonthFilter}
          />
        }
      >
        <TableFrame>
          <table className="w-max min-w-full border-collapse text-[11px]">
            <thead>
              <tr>
                <th
                  rowSpan={2}
                  className="sticky left-0 z-20 bg-[var(--p1)] px-2 py-2 text-left text-white"
                >
                  Prefixo
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
              {prefixes.map((p, pi) => (
                <tr key={p}>
                  <td className="sticky left-0 z-10 bg-[#eef6fa] px-2 py-1 font-bold text-[var(--p1)]">
                    {p}
                  </td>
                  {columns.map((c) => {
                    const st = statusAt(pi, c.day);
                    return (
                      <td
                        key={`${p}-${c.day}`}
                        className="px-0.5 py-1 text-center"
                      >
                        <span
                          className="inline-block h-3.5 w-3.5 rounded-[2px]"
                          style={{
                            background: STATUS_COLOR[st] || STATUS_COLOR.na,
                          }}
                          title={`${p} · ${c.day} · ${st}`}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
        <div className="mt-2 flex flex-wrap gap-3 text-xs font-normal text-[var(--muted)]">
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-2.5 rounded-sm bg-[#7BC67E]" /> Sem falha
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-2.5 rounded-sm bg-[#E89A9A]" /> Falha
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-2.5 rounded-sm bg-[#C5CED6]" /> Fora do período
          </span>
        </div>
      </Panel>
    </div>
  );
}

function dayIso(label: string, year: string) {
  const parts = label.split("/");
  if (parts.length >= 2 && parts[0] && parts[1]) {
    const y = parts[2] || year;
    return `${y}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
  }
  return /^\d{4}-\d{2}-\d{2}/.test(label) ? label.slice(0, 10) : "";
}
