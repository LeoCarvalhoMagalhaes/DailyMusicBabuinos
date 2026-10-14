# Arquitetura, API e modelo de dados

## Princípios

1. **O backend é a autoridade.** Tentativas, validação, pontuação, resultado e estatísticas
   são decididos no servidor. O frontend só exibe o que a API devolve.
2. **Segredo protegido.** A música do dia só sai do servidor depois que a partida termina.
3. **Áudio separado das regras.** O provedor de áudio fica atrás de uma interface
   (`AudioProvider`); falhas de áudio nunca alteram a partida.
4. **Configuração central.** Estágios, pontuação, fuso, janelas de repetição e limites
   vêm de variáveis de ambiente (`backend/app/core/config.py`).

## Fluxo de uma partida

```
Navegador                                API                                   Banco
   │ POST /api/players ───────────────────► cria jogador anônimo ─────────────► players (hash do token)
   │ ◄──────────────────────── token (guardado no localStorage)
   │ POST /api/games/start {category} ────► desafio de hoje existe?  ──não──► sorteio HMAC + filtros
   │                                         └─► grava daily_challenges (único por dia/categoria)
   │ ◄──────────────── estado da partida (sem título/artista)            game_sessions (único por jogador+desafio)
   │ GET /api/games/{id}/audio?stage=1 ───► estágio liberado? ─► provedor ─► corta e remove metadados
   │ ◄──────────────── trecho (audio/mpeg ou audio/wav), sem cache
   │ POST /api/games/{id}/guess {guess, attempt} ─► valida vez, normaliza, compara título/aliases
   │ ◄──────────────── {correct, game}; se acabou, game.answer + estatísticas recalculadas
```

## Endpoints

Todas as rotas ficam sob `/api`. Erros seguem o formato
`{"error": {"code": "...", "message": "..."}}`. Rotas marcadas com 🔑 exigem
`Authorization: Bearer <token>` (ou `X-Player-Token`).

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Saúde da API e do banco (usado pelo host). |
| POST | `/players` | Cria jogador anônimo e devolve o token (limite por IP/hora). |
| GET 🔑 | `/players/me` | Confere o token. |
| GET | `/categories` | As seis categorias. |
| GET | `/daily` | Visão do dia: data, número do desafio, próxima virada, regras, modo de áudio e (com token) o status do jogador em cada categoria. |
| GET | `/daily/{category}` | Informações públicas do desafio de uma categoria. |
| POST 🔑 | `/games/start` | Inicia **ou recupera** a partida do dia (idempotente). |
| GET 🔑 | `/games/{id}` | Estado da partida. |
| POST 🔑 | `/games/{id}/guess` | Palpite `{guess, attempt}`. |
| POST 🔑 | `/games/{id}/skip` | Pula a vez `{attempt}` (consome tentativa). |
| GET 🔑 | `/games/{id}/audio?stage=N` | Trecho do estágio N (só se liberado). |
| GET 🔑 | `/games/{id}/result` | Resultado com a música revelada (409 se em andamento). |
| GET 🔑 | `/statistics` | Estatísticas gerais e por gênero. |
| GET 🔑 | `/history?limit&offset` | Histórico de partidas. |
| GET | `/songs/search?q=` | Sugestões de títulos (catálogo inteiro da edição ativa). |

A documentação interativa (OpenAPI) fica em `/api/docs` fora de produção.

### O que a API impede (e como)

| Abuso | Proteção |
| --- | --- |
| Alterar pontuação pelo frontend | Pontos calculados no servidor a partir da tabela configurada. |
| Consultar o título antes do fim | Nenhum schema de partida em andamento tem título/artista; `reveal_answer` exige partida encerrada; não existe rota que exponha `music_tracks` ou `daily_challenges`. |
| Tentativas ilimitadas | Máximo de N tentativas; número da tentativa esperado no corpo; restrição única `(game_id, attempt_number)`; limitador por jogador. |
| Palpite repetido | Rejeitado (409 `duplicate_guess`) sem consumir tentativa. |
| Sessões inexistentes | 404. IDs malformados também respondem 404. |
| Mexer na partida de outra pessoa | Partidas são filtradas pelo jogador do token; partidas alheias respondem 404 (não confirmamos que existem). |
| Reiniciar desafio concluído | Restrição única `(player_id, challenge_id)`; `start` devolve a partida existente. |
| Manipular a data | O cliente nunca envia data; o dia vem do relógio do servidor no fuso configurado. |
| Ouvir trechos ainda bloqueados | `audio?stage=N` responde 403 `stage_locked`. |
| Força bruta / scraping | Limites por minuto em palpites, áudio e busca; criação de jogador limitada por IP/hora. |

## Modelo de dados

```
catalog_sources (id PK, name, kind[editorial|chart], url, retrieved_on, methodology)
music_tracks    (id PK, slug UNIQUE, edition[main|demo] IDX, title, artist IDX,
                 primary_category, extra_genres JSON, aliases JSON,
                 external_provider, external_id, external_url, cover_url,
                 audio_ref, license_note, availability, availability_checked_at)
catalog_entries (id PK, category IDX, track_id FK, reference_rank NULL, source_id FK, active,
                 UNIQUE(category, track_id))
daily_challenges(id PK, challenge_date IDX, category, edition, track_id FK IDX, status, created_at,
                 UNIQUE(challenge_date, category, edition))
players         (id PK uuid, token_hash UNIQUE IDX, created_at, last_seen_at)
game_sessions   (id PK uuid, challenge_id FK IDX, player_id FK, attempts_used, score,
                 status[in_progress|won|lost], started_at, finished_at,
                 UNIQUE(player_id, challenge_id), IDX(player_id, status))
game_guesses    (id PK, game_id FK, attempt_number, guess_text, normalized, is_skip, is_correct,
                 created_at, UNIQUE(game_id, attempt_number))
player_statistics(player_id FK, category["all"|slug], games_played, wins, total_score,
                 current_streak, best_streak, last_played_date, distribution JSON, updated_at,
                 PK(player_id, category))
```

Mapeamento para as entidades pedidas: **MusicTrack** = `music_tracks` + `catalog_entries`
(posição e fonte por categoria, sem duplicar a faixa quando ela aparece em duas listas);
**DailyChallenge** = `daily_challenges`; **GameSession** = `game_sessions` + `game_guesses`;
**PlayerStatistics** = `player_statistics` (uma linha geral e uma por categoria).

`player_statistics` é um **agregado derivado**: a cada partida concluída ele é recalculado a
partir de `game_sessions` (fonte da verdade). Assim é impossível contar a mesma partida duas
vezes, e o agregado pode ser reconstruído a qualquer momento.

Migrações: `backend/alembic/versions`. A API aplica `alembic upgrade head` ao iniciar
(também disponível em `python -m app.cli migrate`).

## Desafio diário

- **Fuso:** `CHALLENGE_TIMEZONE=America/Sao_Paulo`. Brasília não tem horário de verão desde
  2019, então a virada é sempre 00:00 local (03:00 UTC). O servidor calcula `today()` nesse
  fuso; nada depende do relógio do aparelho.
- **Seleção:** candidatas da categoria ordenadas por `HMAC-SHA256(CHALLENGE_SECRET,
  "edição|categoria|data|slug")`. Filtros: faixa não usada em nenhuma categoria nos últimos
  `REPEAT_WINDOW_DAYS` (60), nem no mesmo dia em outra categoria; artista não repetido na
  mesma categoria em `ARTIST_COOLDOWN_DAYS` (7). Em catálogos pequenos (modo demo), os filtros
  são relaxados escolhendo a faixa usada há mais tempo.
- **Persistência:** o primeiro acesso do dia grava o desafio. Daí em diante vale o banco,
  mesmo que o catálogo mude. Corridas entre processos são resolvidas pela restrição única.
- **Virada durante a partida:** uma partida iniciada antes da meia-noite pode ser terminada
  depois (ela pertence ao desafio da data em que começou); a sequência de dias usa a data do
  desafio, não a hora do palpite.
- **Número do desafio:** dias desde `LAUNCH_DATE` + 1, exibido na interface e no
  compartilhamento.

## Identidade anônima e persistência

- Token aleatório de 256 bits gerado pelo servidor, guardado no `localStorage`. O banco guarda
  só o SHA-256 do token. O frontend usa uma única promessa de identificação por carregamento
  (evita criar dois jogadores em requisições simultâneas).
- Escolhemos token em cabeçalho (não cookie) porque frontend e API costumam ficar em domínios
  diferentes nos planos gratuitos, e cookies de terceiros são bloqueados por vários
  navegadores. Mitigação de XSS: nenhum script de terceiros, React escapando conteúdo.
- **Limitações:** limpar os dados do site ou trocar de navegador cria um jogador novo (o
  histórico antigo fica órfão no servidor) e permite jogar de novo o dia — inerente a um jogo
  sem login. **Evolução:** tabela de contas vinculada a `players.id`, login por e-mail
  (link mágico) ou OAuth, e mesclagem de jogadores anônimos.
- **Retenção:** `python -m app.cli purge-inactive --days 400` remove jogadores inativos e
  suas partidas (agendável no host).

## Testes

| Camada | Ferramenta | O que cobre |
| --- | --- | --- |
| Backend | pytest (107 testes, SQLite e PostgreSQL) | seleção diária, consistência entre jogadores e servidores, virada à meia-noite, validação e normalização, tentativas, pontuação, fim por acerto/derrota, proteção contra tentativas extras, isolamento entre jogadores, sigilo da resposta, estatísticas e sequências, persistência após reinício, corte de MP3/WAV, provedor Deezer com respostas simuladas e falhas, limites de requisição, CORS, configuração |
| Frontend | Vitest + Testing Library (27) | texto de compartilhamento sem spoiler, Web Share e fallback, autocomplete por teclado, player e trechos bloqueados, tentativas, resultado, hook da partida (duplo clique, sincronização, duplicados) |
| Ponta a ponta | Playwright (12 = 6 fluxos × desktop e celular) | partida vencida com áudio, erro, recarga, acerto e compartilhamento; derrota e estatísticas; palpite repetido; offline; páginas estáticas e 404; ausência de rolagem horizontal |

Comandos em [README.md](../README.md#testes).
