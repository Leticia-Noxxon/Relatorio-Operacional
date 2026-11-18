# Relatório Operacional CFTV

Pacote essencial do painel web.

## Rodar o painel

```bash
cd web
npm install
npm run dev
```

Abra http://localhost:3000

## Estrutura

- `web/` — app Next.js (UI + APIs)
- `web/data/datasets/` — JSON dos relatórios
- `scripts/` — pipeline de coleta/exportação
- `generate_report.py` — análise Jotform/executivo
- `data/web/` — cópia dos JSON exportados

## Observação

Este ZIP não inclui `node_modules`, PDFs, PPTX nem dumps grandes do NxNet.
