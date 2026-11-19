"use client";

import { useMemo, useState } from "react";
import { Panel, TableFrame, VerticalBars } from "@/components/Dashboard";

type RetornoData = {
  trocas: number;
  buckets: { name: string; count: number }[];
  rows: Record<string, string>[];
};

const PAGE_SIZES = [5, 10, 20, 40, 60];

export function RetornoView({
  data,
  range,
}: {
  data: RetornoData;
  range?: { start: string; end: string };
}) {
  const buckets = data.buckets || [];
  const rows = (data.rows || []).filter((row) => {
    if (!range) return true;
    const iso = brDate(row["Data da troca"] || "");
    return !iso || (iso >= range.start && iso <= range.end);
  });
  const shownBuckets = useMemo(() => {
    if (!range) return buckets;
    const counts = new Map<string, number>();
    for (const name of ["sem falha", "1 a 7 dias", "8 a 15 dias", "16 a 30 dias", "31 a 60 dias", "acima de 60 dias"]) {
      counts.set(name, 0);
    }
    for (const row of rows) {
      const name = (row.Faixa || "").trim();
      if (!name) continue;
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    return [...counts.entries()].map(([name, count]) => ({ name, count }));
  }, [range, rows, buckets]);
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);

  const pageRows = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [rows, safePage, pageSize]);

  const from = rows.length ? (safePage - 1) * pageSize + 1 : 0;
  const to = Math.min(safePage * pageSize, rows.length);

  return (
    <div className="space-y-3">
      <Panel
        title="Retorno de falhas"
        right={
          <div className="rounded-lg bg-[var(--p4)] px-3 py-1.5 text-sm font-extrabold text-[var(--p1)]">
            Total: {range ? rows.length : data.trocas ?? rows.length}
          </div>
        }
      >
        <VerticalBars
          items={shownBuckets.map((b) => ({ label: b.name, value: b.count }))}
        />
      </Panel>

      <Panel title="Detalhe das trocas">
        <TableFrame>
          <table className="w-full min-w-[820px] border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-center">Prefixo</th>
                <th className="px-3 py-2 text-left">Nome</th>
                <th className="px-3 py-2 text-left">Garagem</th>
                <th className="px-3 py-2 text-center">Data da troca</th>
                <th className="px-3 py-2 text-center">Data da falha</th>
                <th className="px-3 py-2 text-center">Dias até a falha</th>
                <th className="px-3 py-2 text-center">Faixa</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r, i) => (
                <tr
                  key={`${r.Prefixo}-${i}`}
                  className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                >
                  <td className="px-3 py-2 text-center font-bold">{r.Prefixo}</td>
                  <td className="px-3 py-2">{r.Nome || "—"}</td>
                  <td className="px-3 py-2">{r.Garagem}</td>
                  <td className="px-3 py-2 text-center">{r["Data da troca"]}</td>
                  <td className="px-3 py-2 text-center">
                    {r["Data da falha (OFFLINE)"] || "—"}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {r["Dias até a falha"] || "—"}
                  </td>
                  <td className="px-3 py-2 text-center">{r.Faixa}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>

        <div className="mt-3 flex flex-wrap items-center justify-end gap-3 text-xs text-[var(--muted)]">
          <span>
            {from}–{to} de {rows.length}
          </span>
          <label className="inline-flex items-center gap-1.5">
            Por página
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="h-7 rounded border border-[var(--line)] bg-white px-1.5 text-[var(--p1)]"
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <div className="flex gap-1">
            <button
              type="button"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-7 rounded border border-[var(--line)] bg-white px-2.5 font-semibold text-[var(--p1)] disabled:opacity-40"
            >
              ‹
            </button>
            <button
              type="button"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="h-7 rounded border border-[var(--line)] bg-white px-2.5 font-semibold text-[var(--p1)] disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function brDate(value: string) {
  const match = value.match(/(\d{2})\/(\d{2})\/(\d{4})/);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : "";
}
