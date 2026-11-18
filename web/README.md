# Relatórios CFTV — Web

Painel com 5 abas (Executivo, Santa Brígida, SD Card, Conexão, Retorno Switches), filtro de período e botão **Atualizar**.

## Rodar

```bash
# na raiz do monorepo, com deps Python
pip install -r requirements.txt
export NOXXON_EMAIL='...'
export NOXXON_PASSWORD='...'
# opcional: export JOTFORM_API_KEY='...'

cd web
npm install
npm run dev -- -p 3847
```

Abra `http://127.0.0.1:3847`.

## Atualizar

O botão chama `POST /api/refresh`, que executa `scripts/refresh_pipeline.py`:

1. Jotform (`collect_jotform.py` — API key ou fallback local; o link `tables/...` exige login)
2. NxNet histórico + conexão
3. Regeneração dos PDFs/PPTX e prévias

## Segredos

- `NOXXON_EMAIL`
- `NOXXON_PASSWORD`
- `JOTFORM_API_KEY` (recomendado para export automático)
- `JOTFORM_SHARE_URL` (opcional)
