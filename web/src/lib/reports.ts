export type ReportId =
  | "executivo"
  | "santa"
  | "sdcard"
  | "conexao"
  | "retorno";

export type ReportDef = {
  id: ReportId;
  title: string;
  short: string;
  pdf: string;
  previewStem: string;
};

export const REPORTS: ReportDef[] = [
  {
    id: "executivo",
    title: "CFTV",
    short: "CFTV",
    pdf: "relatorio_executivo_cftv.pdf",
    previewStem: "relatorio_executivo_cftv",
  },
  {
    id: "santa",
    title: "Santa Brígida",
    short: "Santa Brígida",
    pdf: "CFTV_Santa_Brigida.pdf",
    previewStem: "CFTV_Santa_Brigida",
  },
  {
    id: "sdcard",
    title: "SD Card",
    short: "SD Card",
    pdf: "Analise_SDCard_Metropole_Expandir.pdf",
    previewStem: "Analise_SDCard_Metropole_Expandir",
  },
  {
    id: "conexao",
    title: "Conexão das Câmeras",
    short: "Conexão das Câmeras",
    pdf: "Conexao_Cameras_por_Unidade.pdf",
    previewStem: "Conexao_Cameras_por_Unidade",
  },
  {
    id: "retorno",
    title: "Retorno de Switches",
    short: "Retorno de Switches",
    pdf: "Retorno_Falhas_Switches_CFTV.pdf",
    previewStem: "Retorno_Falhas_Switches_CFTV",
  },
];

export function getReport(id: string): ReportDef | undefined {
  return REPORTS.find((r) => r.id === id);
}

export const REPORT_IDS: ReportId[] = REPORTS.map((r) => r.id);
