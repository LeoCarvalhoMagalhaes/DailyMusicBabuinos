# Implantação

> Condições dos planos gratuitos consultadas em 14/10/2026. Elas mudam com frequência:
> confira as páginas oficiais antes de publicar.

## Visão geral recomendada

| Peça | Opção recomendada | Alternativas |
| --- | --- | --- |
| API (FastAPI) | **Render** — Web Service com Docker, plano Free | Fly.io, Railway, Koyeb (verifique os planos atuais) |
| Banco PostgreSQL | **Neon** (Free, sem data de expiração) ou Render Postgres Free (expira em 30 dias) | Supabase |
| Frontend estático | **GitHub Pages** (como os outros jogos do autor) | Cloudflare Pages, Netlify, Render Static Site, Vercel (Hobby só para uso pessoal e não comercial) |

Publicação escolhida: o site fica em **https://leocarvalhomagalhaes.github.io/DailyMusicBabuinos/**
(workflow [`pages.yml`](../.github/workflows/pages.yml)) e a API no Render
([`render.yaml`](../render.yaml), Blueprint com API e banco). O GitHub Pages só serve arquivos
estáticos; o servidor continua necessário porque guarda a resposta em segredo, valida os
palpites, corta o áudio e mantém as estatísticas.

## Limitações dos planos gratuitos (o que esperar)

| Serviço | Limitações relevantes | Fonte |
| --- | --- | --- |
| Render Web Service Free | Suspende após **15 min sem tráfego**; a próxima requisição leva **~1 min** para acordar. 750 horas de instância por mês por workspace. | [render.com/docs/free](https://render.com/docs/free) |
| Render Postgres Free | **Expira 30 dias após a criação** (14 dias de carência para virar pago). Só um banco gratuito ativo por workspace; 1 GB. | [render.com/docs/free](https://render.com/docs/free) |
| Neon Free | 100 CU-horas/mês por projeto, computação suspende após 5 min sem uso (acorda na próxima conexão), armazenamento de 0,5 GB por projeto (relatos recentes indicam 1 GB). | [neon.com/pricing](https://neon.com/pricing) |
| Vercel Hobby | Apenas uso pessoal e **não comercial**; ~100 GB de transferência/mês. | página de preços da Vercel |
| Cloudflare Pages | Plano gratuito permite uso comercial; banda generosa. | página de preços da Cloudflare |

Consequências para o jogo:

- **Multiplayer em tempo real:** o Render aceita WebSocket no Web Service (também no plano
  gratuito), sem configuração extra. As conexões e o laço que avança as rodadas ficam em
  memória, então a API deve rodar com **uma instância** (o padrão do plano gratuito). O estado
  das salas e partidas fica no banco: se a API reiniciar, os jogadores reconectam e continuam.
  Detalhes em [06-modos-de-jogo.md](06-modos-de-jogo.md#hospedagem-das-conexões-persistentes).

- O primeiro jogador depois de um período ocioso espera a API acordar (a tela mostra
  "Afinando as guitarras…"). Um monitor externo pingando `/api/health` evita isso, mas consome
  horas de instância.
- Com uma única instância, o limitador de requisições e o cache de prévias ficam em memória
  e zeram quando a API reinicia (comportamento esperado).
- O `render.yaml` usa o Render Postgres Free, que **expira 30 dias após a criação**. Faça
  backup e migre para o Neon antes disso (ou use o Neon desde o início; veja abaixo).

## Variáveis de ambiente

### Backend (`backend/.env.example` tem todas, comentadas)

| Variável | Produção | Observação |
| --- | --- | --- |
| `APP_ENV` | `production` | Desliga `/api/docs` e exige segredo forte. |
| `DATABASE_URL` | URL do PostgreSQL | `postgres://` e `postgresql://` são aceitas. Neon exige `?sslmode=require` na URL (já vem assim no painel). |
| `CHALLENGE_SECRET` | valor aleatório (≥ 32 caracteres) | **Nunca mude depois de lançar**: os desafios já gravados continuam, mas a ordem dos próximos muda. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AUDIO_PROVIDER` | `deezer` (ou `local`/`demo`) | `demo` mantém o modo demonstração. |
| `CORS_ORIGINS` | origem do frontend | No GitHub Pages: `https://leocarvalhomagalhaes.github.io` (sem o caminho). Várias separadas por vírgula. |
| `CHALLENGE_TIMEZONE` | `America/Sao_Paulo` | Fuso da virada diária. |
| `LAUNCH_DATE` | data do lançamento | Define o "Desafio #1". |
| `CLIP_STAGES_SECONDS`, `SCORE_TABLE` | opcional | Mesma quantidade de itens. |
| `RATE_LIMIT_*` | opcional | Limites por minuto/hora (`RATE_LIMIT_AUTH_PER_HOUR` para login e cadastro). |
| `MP_ROUND_SECONDS`, `MP_REVEAL_SECONDS`, `MP_SPEED_BONUS_MAX` | opcional | Tempo da rodada (60), da revelação (8) e bônus máximo (50) do multiplayer. |
| `MP_MIN_PLAYERS`, `MP_MAX_PLAYERS` | opcional | 2 e 8 por padrão. |
| `MP_IDLE_MINUTES`, `MP_ROOM_IDLE_MINUTES` | opcional | Encerramento por inatividade (10 e 30 min). |
| `AUTH_SESSION_DAYS` | opcional | Validade do login (30 dias). |
| `ENDLESS_RECENT_WINDOW` | opcional | Músicas recentes evitadas no modo ilimitado (50). |

### Frontend

| Variável | Valor | Observação |
| --- | --- | --- |
| `VITE_API_BASE_URL` | URL pública da API, sem barra final | Lida **no build**. Em desenvolvimento fica vazia (o Vite faz proxy de `/api`). No GitHub Pages vem da variável do repositório `API_BASE_URL`. |
| `VITE_BASE_PATH` | `/DailyMusicBabuinos/` no GitHub Pages | Subpasta onde o site é servido. Padrão `/`. |
| `VITE_ROUTER` | `hash` no GitHub Pages | Rotas em `#/` (o Pages não reescreve `/desafio/rock` para o `index.html`). Padrão: rotas normais. |

Nenhuma credencial real é versionada. O Deezer não exige chave de API.

## Publicação atual (14/10/2026)

| Peça | Onde | Endereço |
| --- | --- | --- |
| Site | GitHub Pages (workflow `pages.yml`) | https://leocarvalhomagalhaes.github.io/DailyMusicBabuinos/ |
| API | Render, Web Service **criado à mão** (Docker, plano Free) | https://dailymusicbabuinos.onrender.com |
| Banco | Neon, plano Free (sem cartão, sem data de expiração) | connection string só na variável `DATABASE_URL` do Render |

Por que não o Blueprint: o fluxo **Blueprint** do Render pediu cartão (verificação de conta),
mesmo com tudo em `plan: free`. Criar o Web Service manualmente não pede. O `render.yaml`
continua no repositório para quem tiver cartão cadastrado.

Web Service manual no Render: **New → Web Service** → repositório → Branch `main`,
Language `Docker`, Root Directory `backend`, Instance Type **Free**, Health Check Path
`/api/health`, variáveis `DATABASE_URL` (Neon, com `?sslmode=require`), `APP_ENV=production`,
`AUDIO_PROVIDER=deezer`, `CHALLENGE_TIMEZONE=America/Sao_Paulo`,
`CORS_ORIGINS=https://leocarvalhomagalhaes.github.io` e `CHALLENGE_SECRET` (aleatório, nunca
mude). O site recebe a URL da API pela variável do repositório `API_BASE_URL`.

Verificado no ar em 14/10/2026: `/api/health` com `database: ok`; diário com trechos reais
de 1,019 s e 2,011 s, resposta com link do Spotify e partida mantida após recarregar;
ilimitado com a próxima rodada; multiplayer com dois navegadores (desktop e celular),
WebSocket "Ao vivo" nos dois, mesma resposta revelada para ambos e rodada 2 aberta pelo
servidor; nenhum erro de console. O teste criou as contas `teste_claude_a` e
`teste_claude_b` (podem ficar ou ser removidas do banco).

## Passo a passo — GitHub Pages + Render (Blueprint)

1. **API no Render:** entre em <https://render.com> com a conta do GitHub, escolha
   **New → Blueprint** e o repositório `DailyMusicBabuinos` (branch `main`). O Render lê o
   `render.yaml` e cria `musicas-babuinas-db` e `musicas-babuinas-api`, já com
   `CHALLENGE_SECRET` gerado e `CORS_ORIGINS` apontando para o GitHub Pages.
2. A API aplica as migrações e sincroniza o catálogo ao iniciar. Verifique:
   ```bash
   curl https://musicas-babuinas-api.onrender.com/api/health
   # {"status":"ok","database":"ok","audio_provider":"deezer","catalog_edition":"main",...}
   ```
   Se o Render der outro nome à API (URL já em uso), use a URL que ele mostrar nos passos
   seguintes.
3. **Site no GitHub Pages:** em *Settings → Pages* do repositório, escolha a fonte
   **GitHub Actions** e defina a URL da API:
   ```bash
   gh api -X POST repos/LeoCarvalhoMagalhaes/DailyMusicBabuinos/pages -f build_type=workflow
   gh variable set API_BASE_URL --body https://musicas-babuinas-api.onrender.com
   gh workflow run pages.yml          # ou faça um push na main
   ```
4. **Áudio no ambiente publicado:** o plano gratuito do Render não tem Shell. Rode daqui,
   com a *External Database URL* do banco (painel do Render → `musicas-babuinas-db`):
   ```bash
   cd backend
   DATABASE_URL="postgresql://...render.com/babuinos" python -m app.cli check-audio --limit 600
   ```
   O `publish-today` é opcional: a API cria os desafios do dia no primeiro acesso. Se for
   rodá-lo daqui, use o mesmo `CHALLENGE_SECRET` do Render (painel → API → Environment).
5. Abra <https://leocarvalhomagalhaes.github.io/DailyMusicBabuinos/>, jogue uma categoria no
   celular e no computador e compartilhe um resultado. O primeiro acesso depois de 15 min
   parado leva cerca de 1 min (a API gratuita acorda).

Se o domínio do site mudar (outro usuário do GitHub ou domínio próprio), ajuste
`CORS_ORIGINS` na API e, para domínio próprio na raiz, `VITE_BASE_PATH=/`.

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

- **Build da imagem Docker / `docker compose up --build`:** a máquina usada não tem Docker.
  O comando da imagem foi exercitado diretamente contra PostgreSQL (acima), mas o
  `docker build` em si não rodou.
- **Safari/iOS de verdade:** o WebKit do Playwright no Windows não toca MP3 (nem a prévia
  original do Deezer, sem corte), então o áudio real só foi tocado no Chromium. No WebKit
  passam os fluxos do modo demonstração (WAV). O player libera o áudio no próprio toque,
  como o iOS exige; confira num iPhone o play logo após o toque e o volume (no iOS o
  controle de volume some, porque o sistema ignora `audio.volume`).
- **GitHub Actions:** o workflow `.github/workflows/ci.yml` ainda não rodou no GitHub.
