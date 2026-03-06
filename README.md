# ELEITORA 2.0

Estrutura atual do projeto:

- `frontend/`: aplicação React (CRA + CRACO), pronta para deploy no Vercel.
- `backend/`: API FastAPI, pronta para deploy no Render.
- `tests/`: testes E2E (Playwright) e artefatos.
- `memory/`: documentação interna do produto.

## Deploy recomendado

- Frontend: Vercel (raiz do projeto em `frontend`).
- Backend: Render (serviço web Python com raiz em `backend`).

## Backend no Render

Este repositório já inclui `render.yaml` com configuração base do serviço.

Start command:

```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Build command no Render:

```bash
pip install -r requirements.render.txt
```

Variáveis mínimas no Render:

- `MONGO_URL`
- `DB_NAME`
- `JWT_SECRET`
- `CORS_ORIGINS` (ex.: `https://seu-frontend.vercel.app`)

Variáveis opcionais:

- `APP_URL` (URL pública do frontend)
- `CORS_ALLOW_CREDENTIALS` (`true` apenas se realmente usar cookies cross-site)
- `RESEND_API_KEY`
- `SENDER_EMAIL`
- `BB_APP_KEY`
- `BB_CLIENT_ID`
- `BB_CLIENT_SECRET`
- `BB_ENVIRONMENT` (`homologacao` ou `producao`)

## Frontend no Vercel

Dentro de `frontend/` existe `vercel.json` configurado para:

- instalar dependências com `npm install --legacy-peer-deps`;
- gerar build com `npm run build`;
- publicar a pasta `build`;
- fazer fallback SPA para `index.html`.

Variável obrigatória no Vercel:

- `REACT_APP_BACKEND_URL` (ex.: `https://eleitora-backend.onrender.com`)

## Fluxo de integração (Vercel + Render)

1. Suba backend no Render e copie a URL pública (ex.: `https://eleitora-backend.onrender.com`).
2. No Vercel, configure `REACT_APP_BACKEND_URL` com essa URL.
3. No Render, configure `CORS_ORIGINS` com o domínio do Vercel (produção e preview, separados por vírgula).
4. Redeploy dos dois serviços.

Exemplo de `CORS_ORIGINS`:

```text
https://eleitora.vercel.app,https://eleitora-git-main-seu-time.vercel.app
```

## Desenvolvimento local

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

Com isso, use no frontend:

```text
REACT_APP_BACKEND_URL=http://localhost:8000
```
