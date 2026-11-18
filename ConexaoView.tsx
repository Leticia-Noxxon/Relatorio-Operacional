import { KpiCard, Panel } from "@/components/Dashboard";
import { IconBus, IconCamera, IconSd } from "@/components/Icons";

type Row = {
  unidade: string;
  veiculos_problema: number;
  camera_100_offline: number;
  camera_erro_sd: number;
  camera_21_problema: number;
  camera_retirada: number;
  cameras_problema: number;
  veiculos_erro_sd?: number;
};

type ConexaoData = {
  coletado_em?: string;
  totais: {
    veiculos_problema: number;
    cameras_problema: number;
    veiculos_erro_sd?: number;
    cameras_erro_sd?: number;
    unidades: number;
  };
  all: Row[];
};

export function ConexaoView({ data }: { data: ConexaoData }) {
  const rows = data.all || [];
  const totais = data.totais || {
    veiculos_problema: 0,
    cameras_problema: 0,
    veiculos_erro_sd: 0,
    cameras_erro_sd: 0,
    unidades: 0,
  };

  const sums = rows.reduce(
    (acc, r) => {
      acc.veiculos_problema += r.veiculos_problema || 0;
      acc.camera_100_offline += r.camera_100_offline || 0;
      acc.camera_erro_sd += r.camera_erro_sd || 0;
      acc.camera_21_problema += r.camera_21_problema || 0;
      acc.camera_retirada += r.camera_retirada || 0;
      acc.cameras_problema += r.cameras_problema || 0;
      return acc;
    },
    {
      veiculos_problema: 0,
      camera_100_offline: 0,
      camera_erro_sd: 0,
      camera_21_problema: 0,
      camera_retirada: 0,
      cameras_problema: 0,
    },
  );

  const veiculosSd =
    totais.veiculos_erro_sd ??
    rows.reduce(
      (s, r) =>
        s +
        (r.veiculos_erro_sd ??
          Math.min(r.camera_erro_sd || 0, r.veiculos_problema || r.camera_erro_sd || 0)),
      0,
    );
  const camerasSd = totais.cameras_erro_sd ?? sums.camera_erro_sd;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Veículos com problema"
          value={fmt(totais.veiculos_problema)}
          icon={<IconBus />}
        />
        <KpiCard
          label="Câmeras com problema"
          value={fmt(totais.cameras_problema)}
          icon={<IconCamera />}
          iconTone="#fee2e2"
          iconColor="#dc2626"
        />
        <KpiCard
          label="Veículos com erro de SD"
          value={fmt(veiculosSd)}
          icon={<IconSd />}
          iconColor="#2F87B5"
        />
        <KpiCard
          label="Câmeras com erro de SD"
          value={fmt(camerasSd)}
          icon={<span className="text-sm font-bold">!</span>}
          iconTone="#fff7ed"
          iconColor="#ea580c"
        />
      </div>

      <Panel title="Unidades">
        <div className="overflow-auto">
          <table className="w-full min-w-[780px] border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--p1)] text-white">
                <th className="px-3 py-2 text-left">Unidade</th>
                <th className="px-3 py-2 text-center">Veíc. problema</th>
                <th className="px-3 py-2 text-center">100% offline</th>
                <th className="px-3 py-2 text-center">Erro SD</th>
                <th className="px-3 py-2 text-center">Câm. 21</th>
                <th className="px-3 py-2 text-center">Retirada</th>
                <th className="px-3 py-2 text-center">Câm. problema</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.unidade} className={i % 2 ? "bg-[#f5fafc]" : "bg-white"}>
                  <td className="px-3 py-2 font-medium">{r.unidade}</td>
                  <td className="px-3 py-2 text-center">{r.veiculos_problema}</td>
                  <td className="px-3 py-2 text-center">{r.camera_100_offline}</td>
                  <td className="px-3 py-2 text-center">{r.camera_erro_sd}</td>
                  <td className="px-3 py-2 text-center">{r.camera_21_problema}</td>
                  <td className="px-3 py-2 text-center">{r.camera_retirada}</td>
                  <td className="px-3 py-2 text-center font-semibold">
                    {r.cameras_problema}
                  </td>
                </tr>
              ))}
              <tr className="bg-[var(--p4)] font-bold">
                <td className="border-t-2 border-[var(--p1)] px-3 py-2">Total</td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.veiculos_problema}
                </td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.camera_100_offline}
                </td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.camera_erro_sd}
                </td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.camera_21_problema}
                </td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.camera_retirada}
                </td>
                <td className="border-t-2 border-[var(--p1)] px-3 py-2 text-center">
                  {sums.cameras_problema}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function fmt(n: number) {
  return (n || 0).toLocaleString("pt-BR");
}
