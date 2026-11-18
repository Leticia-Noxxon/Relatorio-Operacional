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

type ExecData = {
  period?: { label?: string };
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
  garages: { name: string; maints: number; reinc: number; prefixes?: number }[];
  garage_bucket_problems: {
    name: string;
    buckets: [string, number][];
  }[];
};

export function ExecutivoView({ data }: { data: ExecData }) {
  const kpis = data.kpis || {
    maintenances: 0,
    reincidences: 0,
    prefixes: 0,
    garages: 0,
    cameras_removed: 0,
  };
  const problemBuckets = data.problem_buckets || [];
  const topProblems = data.top_problems || [];
  const topActions = data.top_actions || [];
  const garages = data.garages || [];
  const occ = data.garage_bucket_problems || [];
  const switchN =
    problemBuckets.find(([k]) => k.toLowerCase().includes("switch"))?.[1] || 0;
  const maxP = Math.max(...topProblems.map(([, v]) => v), 1);
  const maxA = Math.max(...topActions.map(([, v]) => v), 1);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Manutenções"
          value={fmt(kpis.maintenances)}
          icon={<IconWrench />}
        />
        <KpiCard
          label="Reincidências"
          value={fmt(kpis.reincidences)}
          icon={<IconRepeat />}
          iconColor="#2F87B5"
        />
        <KpiCard
          label="Prefixos"
          value={fmt(kpis.prefixes)}
          icon={<IconServer />}
          iconColor="#47BCDF"
        />
        <KpiCard
          label="Garagens"
          value={fmt(kpis.garages)}
          icon={<IconWarehouse />}
          iconColor="#2F87B5"
        />
        <KpiCard
          label="Câmeras retirada"
          value={fmt(kpis.cameras_removed)}
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
              {garages.map((g, i) => {
                const pct = g.maints ? (g.reinc / g.maints) * 100 : 0;
                const bad = pct > 20;
                return (
                  <tr
                    key={g.name}
                    className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}
                  >
                    <td className="px-3 py-2 font-medium">{g.name}</td>
                    <td className="px-3 py-2 text-center">{fmt(g.maints)}</td>
                    <td className="px-3 py-2 text-center">
                      {fmt(g.prefixes ?? 0)}
                    </td>
                    <td className="px-3 py-2 text-center">{fmt(g.reinc)}</td>
                    <td
                      className={`px-3 py-2 text-center font-bold ${
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
            items={problemBuckets.map(([label, value]) => ({ label, value }))}
          />
        </Panel>
        <Panel title="Disponibilidade">
          <div className="flex items-center justify-center gap-6 py-2">
            <Doughnut
              online={Math.max(kpis.maintenances - switchN, 0)}
              offline={switchN}
            />
            <div className="space-y-2 text-sm text-[var(--muted)]">
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
              {topProblems.map(([label, value], i) => (
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
              {topActions.map(([label, value], i) => (
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
              {occ.map((g, i) => {
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
                    <td className="px-3 py-2 font-medium">{g.name}</td>
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
