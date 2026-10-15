# Modos de jogo

O jogo tem três modos, apresentados na página inicial. Os três usam **a mesma mecânica**:
seis tentativas, trechos que dobram a cada pista — 0,5, 1, 2, 4, 8 e 16 s — da gravação original (prévias
do Deezer cortadas no servidor e entregues por partes), a mesma validação tolerante de
respostas e a mesma tabela base de pontos (100/80/60/40/20/10). O que muda é de onde vem a
música e como as rodadas se agrupam.

| | Desafio Diário | Modo Ilimitado | Multiplayer |
| --- | --- | --- | --- |
| Quem joga | jogador anônimo | jogador anônimo | conta (cadastro e login) |
| Música | uma por categoria e dia, igual para todos | sorteada a cada rodada, só para você | sorteada por partida, igual para todos da sala |
| Quantas | 6 por dia | sem limite | 18 por partida (6 categorias × 3) |
| Pontos | tabela base | tabela base | tabela base + bônus de velocidade |
| Estatísticas | diário (sequência de dias) | próprias, por categoria e por sessão | classificação da partida |

No código, toda rodada de qualquer modo é uma linha de `game_sessions` com `mode` =
`daily`, `endless` ou `match`. Palpite, pulo, áudio e revelação são as mesmas funções
(`services/game.py`); cada modo só decide qual música entra e quando ela pode ser jogada.

## Palpite do mesmo artista (amarelo)

Nos três modos, um palpite errado que é **outra música do mesmo artista** da resposta fica
**amarelo** ("quase"), com o aviso "Mesmo artista!" e um comentário do Babuíno; no texto de
compartilhamento vira 🟨. O servidor decide: procura no catálogo as músicas com o título
palpitado e compara o artista (inclusive cada parte de parcerias como "A & B"). A marca é
guardada no palpite (`game_guesses.same_artist`). No multiplayer ela aparece só para quem
palpitou; os outros continuam vendo apenas o andamento. A pontuação não muda.

## Desafio Diário

O modo original, sem mudanças de regra:

- Uma música secreta por categoria e por data, a mesma para todos.
- **A virada acontece à meia-noite no horário de Brasília** (`CHALLENGE_TIMEZONE=America/Sao_Paulo`;
  Brasília não tem horário de verão desde 2019, então é sempre 03:00 UTC). O dia é calculado
  no servidor (`Clock.today()`), nunca no aparelho. Teste:
  `test_challenge_changes_exactly_at_midnight_in_sao_paulo`.
- Uma partida começada antes da meia-noite pode ser terminada depois.
- No navegador, a contagem regressiva usa a hora do servidor; ao chegar a zero, a página
  inicial recarrega os desafios, e a página de uma categoria já terminada carrega o desafio
  novo dela.
- Um desafio concluído não pode ser reiniciado (restrição única `(player_id, challenge_id)`).

## Modo Ilimitado

Rodadas solo sem limite, em qualquer das seis categorias.

- **Sorteio no servidor** (`secrets.SystemRandom`) entre as faixas da categoria com áudio
  disponível.
- **Sem repetição recente:** evita as últimas `ENDLESS_RECENT_WINDOW` (50) músicas que o
  jogador ouviu nesse modo e categoria. Quando o catálogo se esgota, volta primeiro a música
  ouvida há mais tempo.
- **Sem spoiler do diário:** nenhuma música que é desafio diário hoje (em qualquer categoria)
  é sorteada. O servidor publica os desafios do dia antes de sortear, se ainda não existirem.
- **Sem trocar de música:** pedir a próxima com uma rodada em andamento devolve a mesma
  rodada. Para passar, é preciso acertar, gastar as seis tentativas ou desistir. Duas
  requisições simultâneas nunca deixam duas rodadas abertas.
- **Sessão:** `run_id` agrupa as rodadas de uma sessão. O placar da sessão mostra pontos,
  músicas acertadas, acertos seguidos e melhor sequência. "Nova sessão" zera o placar.
- **Estatísticas próprias** (geral e por categoria: rodadas, acertos, taxa, pontos, média,
  sequências e distribuição), separadas das do diário. O modo ilimitado não altera o
  desafio diário, o histórico nem as estatísticas dele.

Rotas: `POST /api/endless/next`, `GET /api/endless/runs/{run_id}`, `GET /api/endless/stats`.
Palpite, pulo e áudio usam as rotas `/api/games/{id}/...` do diário.

## Multiplayer

### Contas

- Cadastro com usuário (3 a 20 caracteres `a-z0-9_`), apelido (2 a 24) e senha (8 a 128).
- Senhas com **scrypt** (sal aleatório; parâmetros guardados com o hash). Tokens de login
  aleatórios, com validade de `AUTH_SESSION_DAYS` (30) dias; o banco guarda só o SHA-256.
- O login erra com a mesma mensagem, e o mesmo custo de hash, para usuário inexistente e
  senha errada. Há limite de tentativas por IP e por usuário.
- O token da conta é diferente do token anônimo do jogador. Cada conta tem um jogador próprio,
  dono das suas rodadas multiplayer.

### Salas

- De **2 a 8 jogadores** (`MP_MIN_PLAYERS`, `MP_MAX_PLAYERS`).
- Código de convite de 6 caracteres, gerado com `secrets` num alfabeto sem caracteres
  ambíguos (31⁶ ≈ 887 milhões de combinações). Tentativas de entrar são limitadas por conta.
  O link `/#/multiplayer/sala/CÓDIGO` também serve de convite.
- A sala mostra os jogadores, quem está conectado, quem está pronto e quem é o anfitrião.
- O anfitrião define a ordem das seis categorias e inicia a partida quando há pelo menos dois
  jogadores e todos estão prontos. Se o anfitrião sai, a sala passa para o jogador mais antigo.
- **Estados:** `waiting` (sala de espera, inclusive entre partidas, quando mostra o resultado
  da última), `playing` (partida em andamento) e `closed` (vazia ou inativa).
- Durante uma partida ninguém novo entra (409 `match_in_progress`); só quem já participa
  pode voltar.

### Partida

- **18 rodadas: 3 músicas de cada categoria**, na ordem da sala. As músicas são sorteadas no
  servidor ao iniciar, sem repetição dentro da partida e sem músicas que são desafio diário
  hoje.
- **Todos recebem a mesma música** em cada rodada. Cada jogador tem as suas seis tentativas e
  os seus trechos (uma `game_session` por jogador e rodada, com restrição única
  `(player_id, match_round_id)`).
- **Fases de cada rodada:**
  1. `playing`: palpites abertos por até `MP_ROUND_SECONDS` (60 s) ou até todos os jogadores
     ativos terminarem;
  2. `reveal`: a resposta aparece para todos ao mesmo tempo por `MP_REVEAL_SECONDS` (8 s); quem
     não terminou fica com 0 pontos na rodada;
  3. a próxima rodada começa. Depois da 18ª, a partida termina e a sala volta para a espera.
- O servidor controla o tempo: palpites depois do fim da rodada respondem 409 `round_closed`,
  e o áudio só é servido para a rodada atual e para os trechos liberados.
- **A resposta só aparece na revelação**, inclusive para quem já acertou ou esgotou as
  tentativas antes. O estado enviado a cada jogador mostra dos outros só quantas tentativas
  usaram e se acertaram, nunca o texto digitado.

### Pontuação

```
pontos da rodada = tabela_base[tentativa] + bônus de velocidade    (acerto)
                 = 0                                               (erro, desistência ou tempo esgotado)

tabela_base      = 100, 80, 60, 40, 20, 10   (1ª a 6ª tentativa)
bônus            = floor(MP_SPEED_BONUS_MAX × tempo_restante / MP_ROUND_SECONDS)
                 = floor(50 × tempo_restante / 60)   com os valores padrão
```

- `tempo_restante` é medido no servidor, no momento em que o palpite certo é registrado.
  O cliente não envia pontos nem tempos.
- Exemplos: acerto de primeira com 45 s restantes = 100 + 37 = 137; acerto na terceira
  tentativa com 40 s restantes = 60 + 33 = 93.
- O mesmo envio repetido (duplo clique, rede instável) é recusado pelo número da tentativa e
  pela restrição única no banco, e nunca pontua duas vezes.
- **Classificação:** maior pontuação total; desempate por mais acertos e depois pelo menor
  tempo médio de resposta (só acertos). Mostra posição, apelido, pontos, acertos, pontos e
  acertos por categoria e tempo médio. O vencedor (ou os empatados no topo) ganha a
  apresentação especial do Babuíno do Rock.

### Desconexão, reconexão e saída

- **Desconectar** (fechar a aba, perder a rede) não tira ninguém da partida. As rodadas
  seguem pelo relógio; quem não jogou fica com 0 nelas.
- **Voltar** (abrir de novo a sala, recarregar a página, reconectar o WebSocket) retoma o
  estado completo, inclusive a rodada atual se ainda houver tempo. O membro é único por
  conta e sala (`UNIQUE(room_id, account_id)`) e as rodadas são únicas por jogador, então
  reconectar não duplica jogador nem dá pontos.
- **Sair** durante a partida marca o jogador como "saiu": a rodada atual dele conta como erro,
  ele não segura mais o fim das rodadas e continua no placar. A partida dos outros continua.
  Ele pode voltar à mesma partida enquanto ela estiver ativa.
- **Abandono:** se todos saem, a partida termina como `abandoned` e a sala fecha.
- **Inatividade:** partida sem nenhum jogador presente por `MP_IDLE_MINUTES` (10) termina como
  `abandoned`; sala de espera sem atividade por `MP_ROOM_IDLE_MINUTES` (30) fecha. Quem está
  com o WebSocket aberto conta como presente.

### Tempo real

- **Fonte da verdade:** o banco. O estado da sala e da partida (tabelas `rooms`,
  `room_members`, `matches`, `match_rounds` e as `game_sessions` das rodadas) sobrevive a
  reinícios do servidor.
- **WebSocket** em `/api/mp/ws`. O cliente envia
  `{"type":"auth","token":"…","room":"CÓDIGO"}` (o token não vai na URL, que pode parar em
  logs). O servidor responde com o estado completo e depois manda
  `{"type":"state","state":{…}}` a cada mudança; `{"type":"ping"}` recebe
  `{"type":"pong"}`. Token ou sala inválidos fecham a conexão com o código 4401.
- **Ações por HTTP** (pronto, ordem, iniciar, sair, palpite, pular), validadas no servidor.
  Cada resposta já traz o estado novo para quem agiu.
- **Laço do servidor** (`REALTIME_INTERVAL_SECONDS`, 0,5 s): avança as rodadas vencidas pelo
  relógio, encerra salas inativas e, para cada sala com conexões, envia o estado quando a
  versão da sala muda ou alguém conecta ou desconecta. O estado é montado por jogador.
- **Consistência:** as mudanças de fase usam compare-and-swap
  (`UPDATE … WHERE rodada = N AND fase = X`), então duas requisições simultâneas, ou o laço e
  uma requisição, nunca avançam a mesma rodada duas vezes.
- **No navegador:** reconexão automática com espera crescente (1 s a 10 s); enquanto o
  WebSocket está fora, o estado é consultado a cada 3 s (`GET /api/mp/rooms/{código}`); ao
  voltar para a aba, sincroniza na hora. O cronômetro usa a hora do servidor.

### Hospedagem das conexões persistentes

- O Render (Web Service, inclusive o plano gratuito) aceita WebSocket na mesma porta HTTP, sem
  configuração extra. O frontend no GitHub Pages abre `wss://<api>/api/mp/ws`; WebSocket não
  passa pela regra de CORS, e a sessão é conferida pelo token na primeira mensagem.
- **Uma instância:** as conexões abertas e o laço de tempo real ficam em memória. É o caso
  do plano gratuito. Para escalar para várias instâncias, seria preciso um canal
  compartilhado (por exemplo, Redis pub/sub) para avisar as outras instâncias; o estado já
  está no banco.
- **Plano gratuito:** a API "dorme" após 15 min sem tráfego. Uma partida em andamento mantém
  tráfego (WebSocket e pings a cada 25 s). Se o servidor reiniciar, os clientes reconectam e
  recebem o estado de novo; as rodadas cujo tempo passou durante a queda são fechadas pelo
  relógio.
- Em desenvolvimento, o Vite encaminha `/api` (HTTP e WebSocket) para a API local.

### Rotas

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/api/auth/register` | Cria conta e devolve o token de login. |
| POST | `/api/auth/login` | Login. |
| POST 🔐 | `/api/auth/logout` | Encerra a sessão. |
| GET 🔐 | `/api/auth/me` | Conta atual. |
| POST 🔐 | `/api/mp/rooms` | Cria sala `{category_order?}`. |
| POST 🔐 | `/api/mp/rooms/join` | Entra (ou volta) `{code}`. |
| GET 🔐 | `/api/mp/rooms/{code}` | Estado completo da sala e da partida. |
| POST 🔐 | `/api/mp/rooms/{code}/ready` | `{ready}`. |
| POST 🔐 | `/api/mp/rooms/{code}/order` | Ordem das categorias (anfitrião). |
| POST 🔐 | `/api/mp/rooms/{code}/start` | Inicia a partida (anfitrião). |
| POST 🔐 | `/api/mp/rooms/{code}/leave` | Sai da sala ou da partida. |
| POST 🔐 | `/api/mp/rooms/{code}/guess` | Palpite `{round, attempt, guess}`. |
| POST 🔐 | `/api/mp/rooms/{code}/skip` | Pula `{round, attempt}`. |
| GET 🔐 | `/api/mp/rooms/{code}/rounds/{n}/audio?stage=N` | Trecho da rodada atual. |
| WS | `/api/mp/ws` | Estado em tempo real. |

🔐 = `Authorization: Bearer <token da conta>`.

Suporte: `python -m app.cli reveal --room CÓDIGO` mostra a resposta da rodada atual de uma
sala (usado pelos testes de ponta a ponta).

## Testes por modo

- Diário: `tests/test_game_flow.py`, `tests/test_daily.py`, `tests/test_stats.py`.
- Ilimitado: `tests/test_endless.py`, com:
  - mecânica e pontuação iguais às do diário;
  - sem trocar de música no meio da rodada;
  - sem repetição e sem a música do diário;
  - sem interferir no diário;
  - estatísticas;
  - isolamento entre jogadores;
  - catálogo pequeno;
  - corrida entre duas requisições.
- Multiplayer: `tests/test_multiplayer.py`, com:
  - contas;
  - regras da sala, incluindo o limite de 8 jogadores e a troca de anfitrião;
  - 18 músicas, 3 por categoria, iguais para todos e fora do diário;
  - pontos com bônus calculados no servidor e envio duplicado sem pontos extras;
  - resposta escondida até a revelação;
  - tempo esgotado;
  - áudio só da rodada atual;
  - partida completa com classificação;
  - reconexão sem duplicar;
  - saída sem interromper a partida e abandono;
  - inatividade;
  - transição concorrente;
  - WebSocket (aviso de mudanças e recusa de sessão inválida);
  - fórmula do bônus.
- Migração: `tests/test_migrations.py`, que aplica a 0003 sobre partidas diárias já gravadas.
- Ponta a ponta: `frontend/e2e/modes.spec.ts`, com:
  - os três modos na página inicial;
  - rodadas seguidas do ilimitado sem mexer no diário;
  - multiplayer com dois navegadores, cobrindo cadastro, sala por código, prontidão,
    sincronização pelo WebSocket, áudio por partes, resposta escondida, reconexão
    recarregando a página, revelação simultânea e a rodada seguinte.
