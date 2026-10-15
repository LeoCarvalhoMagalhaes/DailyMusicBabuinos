# 🐒🎸 Músicas Babuínas

**Ouviu? Adivinha!** Um jogo de adivinhação musical com três modos: o **Desafio Diário**
(a cada dia, seis categorias — Rock, Pop, Rap, Country, Eletrônica e Geral — ganham uma música
secreta, a mesma para todos os jogadores), o **Modo Ilimitado** (rodadas solo sem fim) e o
**Multiplayer** (salas de 2 a 8 jogadores disputando 18 músicas em tempo real). Você ouve um trecho de 1 segundo e tem seis tentativas; a cada erro ou pulo, a
música toca um pouco mais. O mascote **Babuíno do Rock** reage a cada jogada.

**Jogue em https://leocarvalhomagalhaes.github.io/DailyMusicBabuinos/** · *[Read in English](README.en.md)*

![Tela inicial](docs/screenshots/inicio-desktop.png)

| Desafio no celular | Resultado |
| --- | --- |
| ![Desafio no celular](docs/screenshots/desafio-celular.png) | ![Resultado](docs/screenshots/resultado-desktop.png) |

## Destaques

- **Três modos com a mesma mecânica:** Desafio Diário (seis desafios iguais para todos, com
  virada à meia-noite de Brasília), Modo Ilimitado (rodadas solo sem repetir músicas e sem
  mexer no diário) e Multiplayer (contas, salas de 2 a 8 com código de convite, 18 músicas —
  3 por categoria —, placar ao vivo por WebSocket, bônus de velocidade, reconexão e
  classificação final). Veja [06 — Modos de jogo](docs/06-modos-de-jogo.md).
- **Pistas exponenciais** (0,5, 1, 2, 4, 8 e 16 s: cada uma dobra a anterior; configuráveis),
  palpite errado do **mesmo artista em amarelo** ("quase"), seis tentativas, botão de
  pular e pontuação 100/80/60/40/20/10.
- **Backend como autoridade:** tentativas, validação e pontos no servidor; a música secreta
  nunca chega ao navegador antes do fim; o áudio é cortado no servidor e entregue sem
  metadados.
- **Respostas tolerantes:** acentos, maiúsculas, pontuação, aliases e pequenos erros de
  digitação, sem confundir músicas parecidas.
- **Músicas reais, por partes:** a lista sai dos streams do Spotify (kworb) e o jogo toca
  trechos crescentes da gravação original; no fim, link para ouvir no Spotify.
- **Estatísticas completas:** taxa de acerto, pontos, média, sequência de dias, distribuição
  por tentativa, desempenho por gênero e histórico.
- **Compartilhamento sem spoiler** com Web Share API e fallback de cópia.
- **Mascote original em SVG** com sete humores (confiante, curtindo o som, dúvida, nervoso,
  comemorando, derrota engraçada e pose de campeão).
- **Mobile first:** sugestões que abrem acima do teclado virtual, controles grandes, estados
  de carregamento, erro e offline.
- **Áudio plugável:** prévias oficiais do Deezer, arquivos licenciados ou **modo
  demonstração** com melodias em domínio público sintetizadas pelo próprio jogo.

## Stack

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router, CSS Modules, Lucide, Fontsource (Bungee + Rubik) |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx, NumPy |
| Banco | PostgreSQL (produção), SQLite (desenvolvimento e testes) |
| Testes | pytest, Vitest + Testing Library, Playwright |
| Deploy | GitHub Pages (site), Render Blueprint (API + PostgreSQL), Docker, GitHub Actions |

## Rodando localmente

Pré-requisitos: Python 3.11+ e Node.js 20+.

```bash
# 1) API (SQLite, sem credenciais)
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # opcional: ajuste as variáveis
uvicorn app.main:app --reload      # http://127.0.0.1:8000  (docs em /api/docs)

# 2) Frontend (em outro terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

As migrações e a carga do catálogo rodam automaticamente quando a API inicia.

**Com PostgreSQL via Docker Compose:** `docker compose up --build` sobe banco e API;
depois rode o frontend com `npm run dev`.

**Músicas reais (padrão):** o jogo toca trechos das gravações originais (prévias oficiais do
Deezer), com o catálogo principal de 6 × 100 músicas. Precisa de internet e não exige chave
de API. Sem internet, use `AUDIO_PROVIDER=demo` no `backend/.env` (melodias sintetizadas).

**Catálogo com as músicas mais ouvidas no Spotify:** gere as listas a partir dos dados do
kworb (uma vez, ~10 min):

```bash
cd backend && python -m app.cli import-kworb && python -m app.cli check-audio --limit 600
```

### Ferramentas de operação

```bash
cd backend
python -m app.cli publish-today              # publica os desafios de hoje
python -m app.cli check-audio --limit 20     # valida prévias no provedor
python -m app.cli reveal --category rock     # mostra a resposta de hoje (suporte)
python -m app.cli sync-catalog               # recarrega o catálogo JSON
python -m app.cli import-kworb               # catálogo a partir dos streams do Spotify (kworb)
python -m app.cli purge-inactive --days 400  # retenção de dados
```

## Testes

```bash
cd backend && pytest                                   # 185 testes (SQLite; 1 só com DEEZER_LIVE=1)
TEST_DATABASE_URL=postgresql://user:senha@localhost:5432/babuinos_test pytest   # mesmos testes no PostgreSQL

cd frontend
npm run typecheck && npm test                          # 41 testes Vitest
npx playwright install chromium                        # uma vez
npm run e2e                                            # 18 testes E2E (desktop + celular)
E2E_WEBKIT=1 npm run e2e                               # + 9 no WebKit (iPhone); antes: npx playwright install webkit
```

Os testes E2E sobem o backend real em modo demonstração (banco descartável) e o frontend,
jogam partidas completas e verificam que não há rolagem horizontal no celular.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [01 — Análise e planejamento](docs/01-analise-e-planejamento.md) | Bandle, escopo, arquitetura, estratégia de áudio e catálogo, riscos |
| [02 — Arquitetura, API e dados](docs/02-arquitetura-api-dados.md) | Endpoints, regras anti-abuso, modelo de dados, fuso horário, identidade anônima, testes |
| [03 — Áudio e catálogo](docs/03-audio-e-catalogo.md) | Provedores, limitações e termos do Deezer, corte do áudio, modo demo, metodologia e atualização do catálogo |
| [04 — Design](docs/04-design.md) | Identidade visual, mascote, telas, componentes, responsividade e acessibilidade |
| [05 — Implantação](docs/05-implantacao.md) | Passo a passo, variáveis de ambiente, limites dos planos gratuitos |
| [06 — Modos de jogo](docs/06-modos-de-jogo.md) | Diário, ilimitado e multiplayer: regras, pontuação, tempo real, reconexão e hospedagem |

## Sobre o áudio e o catálogo (importante)

- **Lista de músicas:** as mais ouvidas no Spotify, segundo os dados públicos do kworb.net
  (`python -m app.cli import-kworb`), com posição, fonte e data registradas. A lista atual
  foi importada em 14/10/2026: 6 × 100 faixas, 519 das 520 com prévia no Deezer.
- **Áudio:** trechos da gravação original, por partes, vindos das prévias oficiais do Deezer.
  O Spotify não é usado como fonte de áudio porque a política para desenvolvedores dele
  proíbe jogos e quizzes.
- O **modo demonstração** (`AUDIO_PROVIDER=demo`) é só para uso offline: melodias em domínio
  público sintetizadas pelo próprio jogo, sinalizadas na interface.
- As prévias do Deezer seguem os termos para desenvolvedores do Deezer (uso pessoal, com
  atribuição). Para uso comercial, contate o Deezer ou use áudio licenciado (`AUDIO_PROVIDER=local`).

## Licença e créditos

Código, textos e o mascote Babuíno do Rock são originais deste projeto. Fontes Bungee e Rubik
(SIL Open Font License), ícones Lucide (ISC). Nomes de artistas e músicas pertencem aos seus
titulares e aparecem apenas para identificação. Projeto independente, inspirado na mecânica de
jogos diários como o Bandle, sem afiliação com ele.
