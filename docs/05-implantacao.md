# Implantação

> Condições dos planos gratuitos consultadas em 14/10/2026. Elas mudam com frequência:
> confira as páginas oficiais antes de publicar.

## Visão geral recomendada

| Peça | Opção recomendada | Alternativas |
| --- | --- | --- |
| API (FastAPI) | **Render** — Web Service com Docker, plano Free | Fly.io, Railway, Koyeb (verifique os planos atuais) |
| Banco PostgreSQL | **Neon** (Free, sem data de expiração) ou Render Postgres Free (expira em 30 dias) | Supabase |
| Frontend estático | **Render Static Site** ou **Cloudflare Pages** | Netlify, Vercel (Hobby só para uso pessoal e não comercial) |

O arquivo [`render.yaml`](../render.yaml) cria API, site e banco de uma vez (Blueprint).

## Limitações dos planos gratuitos (o que esperar)

| Serviço | Limitações relevantes | Fonte |
| --- | --- | --- |
| Render Web Service Free | Suspende após **15 min sem tráfego**; a próxima requisição leva **~1 min** para acordar. 750 horas de instância por mês por workspace. | [render.com/docs/free](https://render.com/docs/free) |
| Render Postgres Free | **Expira 30 dias após a criação** (14 dias de carência para virar pago). Só um banco gratuito ativo por workspace; 1 GB. | [render.com/docs/free](https://render.com/docs/free) |
| Neon Free | 100 CU-horas/mês por projeto, computação suspende após 5 min sem uso (acorda na próxima conexão), armazenamento de 0,5 GB por projeto (relatos recentes indicam 1 GB). | [neon.com/pricing](https://neon.com/pricing) |
| Vercel Hobby | Apenas uso pessoal e **não comercial**; ~100 GB de transferência/mês. | página de preços da Vercel |
| Cloudflare Pages | Plano gratuito permite uso comercial; banda generosa. | página de preços da Cloudflare |

Consequências para o jogo:

- O primeiro jogador depois de um período ocioso espera a API acordar (a tela mostra
  "Afinando as guitarras…"). Um monitor externo pingando `/api/health` evita isso, mas consome
  horas de instância.
- Com uma única instância, o limitador de requisições e o cache de prévias ficam em memória
  e zeram quando a API reinicia (comportamento esperado).
- Se usar Render Postgres Free, **faça backup e migre antes de 30 dias** (ou use Neon desde
  o início).

## Variáveis de ambiente

### Backend (`backend/.env.example` tem todas, comentadas)

| Variável | Produção | Observação |
| --- | --- | --- |
| `APP_ENV` | `production` | Desliga `/api/docs` e exige segredo forte. |
| `DATABASE_URL` | URL do PostgreSQL | `postgres://` e `postgresql://` são aceitas. Neon exige `?sslmode=require` na URL (já vem assim no painel). |
| `CHALLENGE_SECRET` | valor aleatório (≥ 32 caracteres) | **Nunca mude depois de lançar**: os desafios já gravados continuam, mas a ordem dos próximos muda. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AUDIO_PROVIDER` | `deezer` (ou `local`/`demo`) | `demo` mantém o modo demonstração. |
| `CORS_ORIGINS` | URL do frontend | Ex.: `https://musicas-babuinas.onrender.com`. Várias separadas por vírgula. |
| `CHALLENGE_TIMEZONE` | `America/Sao_Paulo` | Fuso da virada diária. |
| `LAUNCH_DATE` | data do lançamento | Define o "Desafio #1". |
| `CLIP_STAGES_SECONDS`, `SCORE_TABLE` | opcional | Mesma quantidade de itens. |
| `RATE_LIMIT_*` | opcional | Limites por minuto/hora. |

### Frontend

| Variável | Valor | Observação |
| --- | --- | --- |
| `VITE_API_BASE_URL` | URL pública da API, sem barra final | Lida **no build**. Em desenvolvimento fica vazia (o Vite faz proxy de `/api`). |

Nenhuma credencial real é versionada. O Deezer não exige chave de API.

## Passo a passo — Render (Blueprint)

1. Faça o push do repositório para o GitHub.
2. No Render: **New → Blueprint**, escolha o repositório. O Render lê `render.yaml` e cria
   `musicas-babuinas-db`, `musicas-babuinas-api` e `musicas-babuinas`.
3. Se os nomes ficarem diferentes (URLs já em uso), ajuste:
   - na API, `CORS_ORIGINS` = URL do site;
   - no site, `VITE_API_BASE_URL` = URL da API, e dispare um novo deploy do site (a variável
     entra no build).
4. A API aplica as migrações (`alembic upgrade head`) e sincroniza o catálogo ao iniciar.
5. Verifique:
   ```bash
   curl https://SUA-API.onrender.com/api/health
   # {"status":"ok","database":"ok","audio_provider":"deezer","catalog_edition":"main",...}
   ```
6. Valide o Deezer no ambiente publicado (Render → API → **Shell**):
   ```bash
   python -m app.cli check-audio --limit 600  # resumo por categoria no fim
   python -m app.cli publish-today            # publica os 6 desafios do dia
   ```
7. Abra o site, jogue uma categoria no celular e no computador, e compartilhe um resultado.

### Usando Neon em vez do Postgres do Render

1. Crie um projeto no Neon e copie a connection string.
2. Remova o bloco `databases` do `render.yaml` (ou ignore o banco criado) e defina
   `DATABASE_URL` manualmente na API com a string do Neon.

### Frontend no Cloudflare Pages ou Netlify

- Diretório raiz: `frontend`; build: `npm ci && npm run build`; saída: `dist`.
- Variável `VITE_API_BASE_URL` com a URL da API.
- O arquivo `public/_redirects` já faz o roteamento de SPA (`/* /index.html 200`).
  Na Vercel, `frontend/vercel.json` cumpre o mesmo papel.
- Inclua a URL final em `CORS_ORIGINS` da API.

## Execução sem Render (qualquer host com Docker)

```bash
docker build -t musicas-babuinas-api ./backend
docker run -p 8000:8000 \
  -e APP_ENV=production \
  -e DATABASE_URL=postgresql://usuario:senha@host:5432/babuinos \
  -e CHALLENGE_SECRET=... -e AUDIO_PROVIDER=deezer \
  -e CORS_ORIGINS=https://seu-site.example \
  musicas-babuinas-api
```

## Tratamento de falhas em produção

| Situação | Comportamento |
| --- | --- |
| Banco fora do ar | `/api/health` responde `degraded`; o host reinicia a instância conforme o health check. |
| Deezer fora do ar / cota | Desafio publicado mesmo assim; áudio responde 503 com mensagem; tentativas preservadas; o jogador pode tentar de novo. |
| Prévia removida | A faixa vira `unavailable` na próxima verificação e deixa de ser sorteada. |
| Erro inesperado | Resposta JSON genérica (sem stack trace) e log no servidor. |

## Manutenção

- Retenção de dados: agende `python -m app.cli purge-inactive --days 400` (Render Cron Job,
  pago, ou execução manual periódica).
- Atualização do catálogo: veja [03-audio-e-catalogo.md](03-audio-e-catalogo.md#como-atualizar-o-catálogo-sem-reescrever-o-jogo).
- Novas migrações: `cd backend && alembic revision --autogenerate -m "descrição"`, revise o
  arquivo gerado e faça o deploy (a API aplica na inicialização).

## O que foi verificado (14/10/2026, Windows 11 com internet)

- **kworb real:** formato das páginas conferido e catálogo de 6 × 100 importado (detalhes em
  [03-audio-e-catalogo.md](03-audio-e-catalogo.md#importação-de-14102026)).
- **Deezer real:** 599 das 600 entradas (519 das 520 faixas únicas) com prévia; corte do MP3
  conferido numa prévia real; auditoria das 519 gravações escolhidas.
- **Partida real em cada categoria** (Chromium desktop e Pixel 7, com API e Vite locais):
  áudio da gravação original tocando por partes (1,019 / 2,011 / 3,004 / ... / 12,016 s),
  trecho seguinte liberado após pular ou errar, 403 ao pedir trecho ainda bloqueado, capa,
  "Ouvir no Spotify" e link do Deezer no acerto, compartilhamento sem a música, partida
  mantida após recarregar, estatísticas atualizadas, sem rolagem horizontal e sem erros no
  console.
- **PostgreSQL 16.15** (binários oficiais portáteis, sem Docker): a suíte do backend passa com
  `TEST_DATABASE_URL`, e a API em `APP_ENV=production` (mesmo comando `uvicorn` da imagem)
  aplicou as migrações, respondeu `/api/health` com `database: ok`, escondeu `/api/docs` e
  serviu uma partida real pelo frontend.
- **E2E no Windows:** a configuração do Playwright passou a funcionar em Windows, Linux e
  macOS. Há um projeto opcional `iphone` (WebKit) com `E2E_WEBKIT=1`.

## O que ainda depende de você

- **Deploy real** (Render/Neon/Cloudflare): depende das suas contas.
- **Build da imagem Docker / `docker compose up --build`:** a máquina usada não tem Docker.
  O comando da imagem foi exercitado diretamente contra PostgreSQL (acima), mas o
  `docker build` em si não rodou.
- **Safari/iOS de verdade:** o WebKit do Playwright no Windows não toca MP3 (nem a prévia
  original do Deezer, sem corte), então o áudio real só foi tocado no Chromium. No WebKit
  passam os fluxos do modo demonstração (WAV). O player libera o áudio no próprio toque,
  como o iOS exige; confira num iPhone o play logo após o toque e o volume (no iOS o
  controle de volume some, porque o sistema ignora `audio.volume`).
- **GitHub Actions:** o workflow `.github/workflows/ci.yml` ainda não rodou no GitHub.
