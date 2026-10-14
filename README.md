# 🐒🎸 Músicas Babuínas

**Ouviu? Adivinha!** Um jogo diário de adivinhação musical: a cada dia, seis categorias
(Rock, Pop, Rap, Country, Eletrônica e Geral) ganham uma música secreta — a mesma para todos
os jogadores. Você ouve um trecho de 1 segundo e tem seis tentativas; a cada erro ou pulo, a
música toca um pouco mais. O mascote **Babuíno do Rock** reage a cada jogada.

*[Read in English](README.en.md)*

![Tela inicial](docs/screenshots/inicio-desktop.png)

| Desafio no celular | Resultado |
| --- | --- |
| ![Desafio no celular](docs/screenshots/desafio-celular.png) | ![Resultado](docs/screenshots/resultado-desktop.png) |

## Destaques

- **Seis desafios diários independentes**, iguais para todos, com virada à meia-noite de
  Brasília e número do desafio.
- **Pistas progressivas** (1, 2, 3, 5, 8 e 12 s, configuráveis), seis tentativas, botão de
  pular e pontuação 100/80/60/40/20/10.
- **Backend como autoridade:** tentativas, validação e pontos no servidor; a música secreta
  nunca chega ao navegador antes do fim; o áudio é cortado no servidor e entregue sem
  metadados.
- **Respostas tolerantes:** acentos, maiúsculas, pontuação, aliases e pequenos erros de
  digitação, sem confundir músicas parecidas.
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
| Deploy | Docker, Render Blueprint, GitHub Actions |

## Rodando localmente

Pré-requisitos: Python 3.11+ e Node.js 20+.

```bash
# 1) API (modo demonstração, SQLite, sem credenciais)
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

**Com as prévias reais do Deezer:** defina `AUDIO_PROVIDER=deezer` no `backend/.env`
(precisa de acesso à internet; não exige chave de API). O jogo passa a usar o catálogo
principal de 6 × 100 músicas.

### Ferramentas de operação

```bash
cd backend
python -m app.cli publish-today              # publica os desafios de hoje
python -m app.cli check-audio --limit 20     # valida prévias no provedor
python -m app.cli reveal --category rock     # mostra a resposta de hoje (suporte)
python -m app.cli sync-catalog               # recarrega o catálogo JSON
python -m app.cli purge-inactive --days 400  # retenção de dados
```

## Testes

```bash
cd backend && pytest                                   # 107 testes (SQLite)
TEST_DATABASE_URL=postgresql://user:senha@localhost:5432/babuinos_test pytest   # mesmos testes no PostgreSQL

cd frontend
npm run typecheck && npm test                          # 27 testes Vitest
npx playwright install chromium                        # uma vez
npm run e2e                                            # 12 testes E2E (desktop + celular)
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

## Sobre o áudio e o catálogo (importante)

- O **modo demonstração** (padrão) usa melodias em domínio público com arranjos sintetizados
  pelo próprio jogo. Ele é sinalizado na interface e **não** é o catálogo definitivo.
- O **catálogo principal** é uma **curadoria editorial** documentada de 100 músicas por
  categoria — não um ranking oficial, e sem posições numéricas inventadas.
- As prévias do Deezer seguem os termos para desenvolvedores do Deezer (uso pessoal, com
  atribuição). Para uso comercial, contate o Deezer ou use áudio licenciado (`AUDIO_PROVIDER=local`).

## Licença e créditos

Código, textos e o mascote Babuíno do Rock são originais deste projeto. Fontes Bungee e Rubik
(SIL Open Font License), ícones Lucide (ISC). Nomes de artistas e músicas pertencem aos seus
titulares e aparecem apenas para identificação. Projeto independente, inspirado na mecânica de
jogos diários como o Bandle, sem afiliação com ele.
