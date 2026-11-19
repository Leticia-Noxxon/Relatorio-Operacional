"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  IconBus,
  IconCalendar,
  IconChart,
  IconFilter,
  IconPdf,
  IconRefresh,
  IconSd,
  IconSwitch,
  IconWifi,
} from "@/components/Icons";
import { ConexaoView } from "@/components/reports/ConexaoView";
import { ExecutivoView } from "@/components/reports/ExecutivoView";
import { RetornoView } from "@/components/reports/RetornoView";
import { SantaView } from "@/components/reports/SantaView";
import { SdCardView } from "@/components/reports/SdCardView";
import { readJson } from "@/lib/http";
import {
  REPORT_IDS,
  REPORTS,
  type ReportId,
} from "@/lib/reports";

type StatusPayload = {
  ok?: boolean;
  running?: boolean;
  updated_at_label?: string;
  start?: string;
  end?: string;
  message?: string;
  error?: string;
};

type DataBundle = Partial<Record<ReportId, Record<string, unknown>>>;

const TAB_ICON: Record<ReportId, ReactNode> = {
  executivo: <IconChart size={15} />,
  santa: <IconBus size={15} />,
  sdcard: <IconSd size={15} />,
  conexao: <IconWifi size={15} />,
  retorno: <IconSwitch size={15} />,
};

/** GitHub Pages: sem rotas de API. Os JSON estáticos são servidos em /data. */
const STATIC_EXPORT = process.env.NEXT_PUBLIC_GITHUB_PAGES === "true";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

function statusUrl() {
  if (STATIC_EXPORT) return `${BASE_PATH}/data/web_status.json?v=${Date.now()}`;
  return "/api/status";
}

function datasetUrl(id: string) {
  if (STATIC_EXPORT) return `${BASE_PATH}/data/datasets/${id}.json?v=${Date.now()}`;
  return `/api/data/${id}?t=${Date.now()}`;
}

async function clearBrowserCaches() {
  try {
    window.localStorage.clear();
  } catch {
    /* armazenamento indisponível */
  }
  try {
    window.sessionStorage.clear();
  } catch {
    /* armazenamento indisponível */
  }
  if ("serviceWorker" in navigator) {
    const regs = await navigator.serviceWorker.getRegistrations();
    await Promise.all(regs.map((reg) => reg.unregister()));
  }
  if ("caches" in window) {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
  }
}

export default function HomePage() {
  const [tab, setTab] = useState<ReportId>("executivo");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [start, setStart] = useState("2026-09-05");
  const [end, setEnd] = useState("2026-11-17");
  const [applied, setApplied] = useState({ start: "2026-09-05", end: "2026-11-17" });
  const seededRange = useRef(false);
  const [busy, setBusy] = useState(false);
  const [busyKind, setBusyKind] = useState<"refresh" | "filter" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [bundle, setBundle] = useState<DataBundle>({});
  const [loadingBundle, setLoadingBundle] = useState(true);
  const [mounted, setMounted] = useState(false);

  const active = useMemo(() => REPORTS.find((r) => r.id === tab)!, [tab]);
  const tabData = bundle[tab] || null;

  const loadStatus = useCallback(async () => {
    const res = await fetch(statusUrl(), { cache: "no-store" });
    const parsed = await readJson<StatusPayload>(res);
    if (!parsed.ok) throw new Error(parsed.error);
    const payload = parsed.data;
    setStatus(payload);
    const nextStart = payload.start ? payload.start.slice(0, 10) : start;
    const nextEnd = payload.end ? payload.end.slice(0, 10) : end;
    if (payload.start) setStart(nextStart);
    if (payload.end) setEnd(nextEnd);
    if (!seededRange.current) {
      seededRange.current = true;
      setApplied({ start: nextStart, end: nextEnd });
    }
    return payload;
  }, []);

  const loadAllData = useCallback(async () => {
    setLoadingBundle(true);
    setError(null);
    try {
      const results = await Promise.all(
        REPORT_IDS.map(async (id) => {
          const res = await fetch(datasetUrl(id), {
            cache: "no-store",
          });
          const parsed = await readJson<Record<string, unknown>>(res);
          if (!parsed.ok) throw new Error(parsed.error);
          if (!res.ok) {
            const err = (parsed.data as { error?: string })?.error;
            throw new Error(err || `Falha ao carregar ${id}`);
          }
          return [id, parsed.data] as const;
        }),
      );
      const next: DataBundle = {};
      for (const [id, payload] of results) next[id] = payload;
      setBundle(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingBundle(false);
    }
  }, []);

  useEffect(() => {
    setMounted(true);
    Promise.all([loadStatus(), loadAllData()]).catch((e) =>
      setError(String(e)),
    );
  }, [loadStatus, loadAllData]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(t);
  }, [toast]);

  async function onRefresh() {
    if (STATIC_EXPORT) {
      setBusy(true);
      setBusyKind("refresh");
      setError(null);
      setToast(null);
      try {
        await clearBrowserCaches();
        const next = new URL(window.location.href);
        next.searchParams.set("v", String(Date.now()));
        window.location.replace(next.toString());
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setBusy(false);
        setBusyKind(null);
      }
      return;
    }
    setBusy(true);
    setBusyKind("refresh");
    setError(null);
    setToast(null);
    try {
      const res = await fetch("/api/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, end }),
      });
      const parsed = await readJson<{ ok?: boolean; error?: string }>(res);
      if (!parsed.ok) throw new Error(parsed.error);
      const payload = parsed.data;
      if (!res.ok || !payload.ok) {
        throw new Error(payload.error || "Falha na atualização");
      }
      await loadStatus();
      await loadAllData();
      setToast("Atualização concluída");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await loadStatus().catch(() => undefined);
    } finally {
      setBusy(false);
      setBusyKind(null);
    }
  }

  async function onPdf() {
    const full =
      applied.start === (status?.start || start).slice(0, 10) &&
      applied.end === (status?.end || end).slice(0, 10);
    const href = `${STATIC_EXPORT ? BASE_PATH : ""}/pdfs/${active.pdf}`;
    if (full) {
      try {
        const res = await fetch(href, { method: "HEAD" });
        if (res.ok) {
          const link = document.createElement("a");
          link.href = href;
          link.download = active.pdf;
          document.body.appendChild(link);
          link.click();
          link.remove();
          return;
        }
      } catch {
        /* cai para impressão */
      }
    }
    window.print();
  }

  function onApplyFilter() {
    setApplied({ start, end });
    setToast("Período aplicado");
    setError(null);
  }

  return (
    <div className="min-h-screen font-[family-name:var(--font-sans)]">
      <header className="no-print sticky top-0 z-30 px-3 pt-3 md:px-5 md:pt-4">
        <div className="mx-auto max-w-[1500px] rounded-2xl border border-[var(--line)] bg-white px-2.5 py-2 shadow-[0_8px_24px_rgba(19,84,135,.08)] md:px-3 md:py-2.5">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-3 xl:flex-nowrap">
            <nav
              className="flex min-w-0 shrink-0 items-center gap-1.5 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              aria-label="Relatórios"
            >
              {REPORTS.map((r) => {
                const activeTab = r.id === tab;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setTab(r.id)}
                    className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-semibold transition md:h-10 md:px-3 ${
                      activeTab
                        ? "bg-[#135487] text-white"
                        : "bg-[#B0E1F1] text-[#135487] hover:brightness-[0.97]"
                    }`}
                  >
                    <span className="opacity-90">{TAB_ICON[r.id]}</span>
                    <span className="whitespace-nowrap">{r.short}</span>
                  </button>
                );
              })}
            </nav>

            <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between lg:justify-end xl:gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-1.5 rounded-xl border-2 border-[#85B0C6] bg-[#f3f8fb] p-1.5 sm:flex-nowrap">
                <label className="relative inline-flex h-8 items-center">
                  <span className="pointer-events-none absolute left-2 text-[#2F87B5]">
                    <IconCalendar />
                  </span>
                  <input
                    type="date"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    aria-label="Data inicial"
                    className="h-8 w-[8.6rem] rounded-md border border-[#85B0C6] bg-white pl-7 pr-1 text-[12px] text-[#0f2740] outline-none focus:border-[#2F87B5] md:w-[9.2rem] md:text-[13px]"
                  />
                </label>
                <span className="hidden text-[#2F87B5] sm:inline">–</span>
                <label className="relative inline-flex h-8 items-center">
                  <span className="pointer-events-none absolute left-2 text-[#2F87B5]">
                    <IconCalendar />
                  </span>
                  <input
                    type="date"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    aria-label="Data final"
                    className="h-8 w-[8.6rem] rounded-md border border-[#85B0C6] bg-white pl-7 pr-1 text-[12px] text-[#0f2740] outline-none focus:border-[#2F87B5] md:w-[9.2rem] md:text-[13px]"
                  />
                </label>
                <button
                  type="button"
                  onClick={onApplyFilter}
                  title="Filtrar o período na tela"
                  aria-label="Filtrar período"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#85B0C6] bg-white text-[#2F87B5]"
                >
                  <IconFilter />
                </button>
                <button
                  type="button"
                  onClick={onPdf}
                  title="Baixar o PDF desta aba ou imprimir o recorte filtrado"
                  aria-label="Download de PDF"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#85B0C6] bg-white text-[#135487]"
                >
                  <IconPdf />
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
                <div className="inline-flex items-center gap-1.5 text-[12px] text-[#5b6b7c] md:text-[13px]">
                  <IconRefresh size={14} className="text-[#5b6b7c]" />
                  <span>
                    Atualizado{" "}
                    <strong className="font-semibold text-[#0f2740]">
                      {status?.updated_at_label || "—"}
                    </strong>
                  </span>
                </div>
                {/* No Pages, recarrega os JSON publicados. No dev, a coleta continua desabilitada. */}
                <button
                  type="button"
                  onClick={onRefresh}
                  disabled={!STATIC_EXPORT || busy}
                  title={
                    STATIC_EXPORT
                      ? "Recarregar os dados publicados"
                      : "Atualização desabilitada neste ambiente"
                  }
                  className={`inline-flex h-9 items-center gap-2 rounded-lg bg-[#16A34A] px-3 text-[13px] font-semibold text-white shadow-sm md:h-10 md:px-3.5 ${
                    !STATIC_EXPORT || busy ? "cursor-not-allowed opacity-50" : ""
                  }`}
                >
                  <IconRefresh size={16} />
                  Atualizar dados
                </button>
              </div>
            </div>
          </div>

          {error ? (
            <div className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </div>
          ) : null}
        </div>
      </header>

      {toast ? (
        <div
          role="status"
          className="toast-in fixed bottom-5 right-5 z-50 rounded-lg bg-[#16A34A] px-4 py-3 text-sm font-semibold text-white shadow-lg"
        >
          {toast}
        </div>
      ) : null}

      <main className="mx-auto max-w-[1500px] px-3 py-2 md:px-5 md:py-3">
        <h1 className="mb-2 text-xl font-extrabold text-[#135487] md:text-[22px]">
          {active.title}
        </h1>

        {!mounted || loadingBundle ? (
          <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-dashed border-[var(--line)] bg-white text-sm text-[var(--muted)]">
            Carregando painel…
          </div>
        ) : !tabData ? (
          <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-dashed border-[var(--line)] bg-white text-sm text-[var(--muted)]">
            Sem dados para esta aba. Clique em Atualizar dados.
          </div>
        ) : (
          <ErrorBoundary label={active.short} key={tab}>
            <ReportBody id={tab} data={tabData} range={applied} />
          </ErrorBoundary>
        )}
      </main>
    </div>
  );
}

function ReportBody({
  id,
  data,
  range,
}: {
  id: ReportId;
  data: Record<string, unknown>;
  range: { start: string; end: string };
}) {
  if (id === "executivo") return <ExecutivoView data={data as never} range={range} />;
  if (id === "santa") return <SantaView data={data as never} range={range} />;
  if (id === "sdcard") return <SdCardView data={data as never} range={range} />;
  if (id === "conexao") return <ConexaoView data={data as never} range={range} />;
  return <RetornoView data={data as never} range={range} />;
}
