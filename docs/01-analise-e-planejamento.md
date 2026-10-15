# Etapa 1 — Análise e planejamento

> Data da análise: 14/10/2026.

## Limitação da análise

O ambiente de desenvolvimento usado neste projeto **bloqueia o acesso** a `bandle.app`,
`api.deezer.com` e `itunes.apple.com` (o proxy de saída responde 403, e a ferramenta de
leitura de páginas também não resolve esses domínios). Por isso:

- a análise do Bandle abaixo vem de **fontes públicas secundárias** (listagem na App Store,
  Google Play e guias especializados), não da navegação direta no site;
- a integração com o Deezer foi implementada contra o formato documentado da API e testada
  com respostas simuladas. Em 14/10/2026 ela foi validada contra o serviço real, numa
  máquina com internet (veja [03-audio-e-catalogo.md](03-audio-e-catalogo.md) e
  [05-implantacao.md](05-implantacao.md)).

Fontes consultadas: [Bandle na App Store](https://apps.apple.com/us/app/bandle-guess-the-song-quiz/id6471419531),
[Bandle no Google Play](https://play.google.com/store/apps/details?id=com.bandlegame.bandleguessasong),
[How-To Geek](https://www.howtogeek.com/bandle-the-daily-music-quiz/),
[dailydle.org](https://www.dailydle.org/games/bandle).

## 1. Resumo funcional do Bandle

| Aspecto | Comportamento observado |
| --- | --- |
| Desafio | Uma música por dia, a mesma para todos os jogadores. |
| Tentativas | 6. |
| Pistas | Começa com **um instrumento** (geralmente bateria ou baixo). Cada erro ou **pulo** acrescenta uma camada (baixo, guitarra, teclado, voz…). Pelo que se observa, as faixas são regravações com instrumentos separados, o que permite revelar por camada. |
| Resposta | Busca com sugestões; o jogador escolhe um título da lista. |
| Pontuação | Quanto menos camadas, melhor o resultado. |
| Dicas extras | Ano de lançamento, gênero ou número de visualizações aparecem no topo. |
| Pós-jogo | Revelação da música, compartilhamento de resultado sem spoiler, estatísticas e sequência. |
| Monetização | Pacotes temáticos e arquivo de dias anteriores pagos; versão gratuita limitada. |
| Virada do dia | Meia-noite no fuso local do jogador (segundo um dos guias). |

**O que torna o jogo divertido:** a sensação de "eu sei essa!" com pouca informação, a
tensão crescente a cada pista, o ritual diário igual para todos e o resultado compartilhável
que gera conversa sem estragar a surpresa.

## 2. Escopo do Músicas Babuínas (MVP implementado)

Reproduzimos os conceitos funcionais com implementação, identidade e textos próprios:

- Seis categorias independentes (Rock, Pop, Rap, Country, Eletrônica, Geral), cada uma com
  seu desafio diário.
- **Pistas por duração** (0,5, 1, 2, 4, 8 e 16 s, dobrando a cada pista; configuráveis) em vez de camadas de
  instrumentos: prévias licenciadas de serviços musicais não trazem faixas separadas.
- Seis tentativas; pular consome uma tentativa; palpite repetido não conta; falha de áudio
  nunca consome tentativa.
- Resposta = **título da música**, com aliases documentados, tolerância a acentos,
  maiúsculas, pontuação e pequenos erros de digitação.
- Pontuação 100/80/60/40/20/10 (derrota = 0), configurável.
- Estatísticas completas, histórico, sequência de dias e desempenho por gênero.
- Compartilhamento sem spoiler (Web Share API + cópia).
- Mascote original **Babuíno do Rock** com 7 humores que reagem à partida.
- Backend como autoridade: a resposta secreta nunca vai ao navegador antes do fim.
- Identidade anônima (sem cadastro) com caminho para contas no futuro.

Fora do MVP (documentado como evolução): contas com login e sincronização entre aparelhos,
painel administrativo, modo "arquivo" de dias anteriores, dicas extras (ano/gênero),
internacionalização.

## 3. Arquitetura recomendada (e adotada)

```
┌──────────────────────────┐   HTTPS (JSON + áudio)   ┌──────────────────────────────┐
│ Frontend (React+TS+Vite) │ ───────────────────────► │ API FastAPI (Python 3.13)    │
│ site estático            │   Authorization: Bearer  │ ├─ regras do jogo (serviços) │
│ - telas e mascote        │ ◄─────────────────────── │ ├─ seleção diária (HMAC)     │
│ - player de pistas       │   trecho cortado (MP3/   │ ├─ camada de áudio           │──► Deezer API / CDN
│ - autocomplete           │   WAV) sem metadados     │ │   (deezer | local | demo)  │    (prévias 30 s)
└──────────────────────────┘                          │ └─ SQLAlchemy + Alembic      │
                                                      └──────────────┬───────────────┘
                                                                     │
                                                      PostgreSQL (produção) / SQLite (dev)
```

- **Frontend:** React 19, TypeScript, Vite, React Router, CSS Modules, Lucide (ISC).
  Estado com hooks próprios (o jogo é simples; não justifica Redux/React Query).
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx (Deezer), NumPy (síntese do
  modo demo). Sem Redis: o limitador de requisições é em memória (instância única no plano
  gratuito), com a interface pronta para trocar.
- **Banco:** PostgreSQL em produção, SQLite em desenvolvimento e testes. A suíte roda nos dois.

Detalhes em [02-arquitetura-api-dados.md](02-arquitetura-api-dados.md).

## 4. Estratégia para áudio e licenciamento

Avaliação das fontes (detalhes em [03-audio-e-catalogo.md](03-audio-e-catalogo.md)):

| Fonte | Situação verificada | Decisão |
| --- | --- | --- |
| **Deezer API pública** | Prévias oficiais de ~30 s em MP3, sem chave de API. Termos para desenvolvedores: uso gratuito para páginas e aplicações pessoais, com atribuição; uso comercial requer contato com o Deezer. | **Provedor principal.** |
| Spotify | A política para desenvolvedores (15/05/2025) proíbe jogos e quizzes; `preview_url` não é retornado para apps novos desde 27/11/2024; modo de desenvolvimento limitado a 5 usuários Premium. | **Fonte da lista de músicas** (streams via kworb) e link "Ouvir no Spotify"; **não** é fonte de áudio. |
| iTunes Search API | Oferece prévias, mas a documentação não pôde ser consultada deste ambiente e os termos exigem uso promocional com link para a loja. | Alternativa futura, via a mesma interface. |
| YouTube / scraping | Extrair áudio viola os termos de uso. | Proibido. |
| Arquivos próprios/licenciados | Viável se houver licença. | **Provedor `local`** implementado. |
| Domínio público | Composições livres, gravações próprias. | **Modo demonstração** (síntese própria). |

Como o servidor entrega o áudio: ele baixa a prévia, **corta no estágio liberado** (quadros
MP3 ou amostras WAV), **remove metadados** (ID3, quadro Xing/Info) e envia só esse trecho.
O navegador nunca recebe a URL da prévia nem o arquivo completo durante a partida.

## 5. Estratégia para o catálogo Top 100

Não existe uma fonte única, gratuita e redistribuível de "Top 100" confiável para os seis
gêneros com sobreposição adequada ao público brasileiro. Por isso:

- O catálogo inicial era uma **curadoria editorial documentada** de 100 faixas por
  categoria. Desde 14/10/2026 as listas vêm dos streams do Spotify publicados pelo kworb
  (520 faixas únicas; a Geral compartilha 77 com os gêneros).
- **Nenhuma posição de ranking foi inventada:** faixas de fontes `editorial` têm `rank` nulo.
  O carregador **rejeita** posição numérica que não venha de uma fonte do tipo `chart`.
- Cada arquivo registra fonte, tipo, data de consulta e metodologia.
- Para trocar por um ranking documentado, basta criar uma fonte `chart` com URL e data e
  preencher `rank` — sem mudar código.

## 6. Estrutura de pastas

```
backend/
  app/
    api/            rotas, dependências e conversão para os contratos públicos
    audio/          provedores (deezer, local, demo), corte de MP3/WAV, sintetizador
    core/           configuração, erros, relógio, segurança, limitador, categorias
    data/           catálogo JSON (catalog/, demo/) e partituras do modo demo (scores/)
    database/       engine, sessões e migração programática
    models/         entidades SQLAlchemy
    repositories/   consultas de jogadores e partidas
    schemas/        contratos Pydantic
    services/       regras: respostas, pontuação, desafio diário, partida, estatísticas, catálogo
    cli.py          ferramentas de operação
  alembic/          migrações
  tests/            pytest (SQLite e PostgreSQL)
frontend/
  src/
    components/     Mascot, AudioPlayer, GuessInput, Attempts, ResultPanel, CategoryCard, Layout…
    hooks/          usePlayer, useGame, useAudioPlayer, useDaily, useCountdown, useOnlineStatus
    pages/          Home, Challenge, Stats, Rules, About, NotFound
    services/       cliente HTTP e armazenamento local
    types/ utils/ styles/ test/
  e2e/              Playwright (desktop e celular)
docs/               esta documentação
```

## 7. Plano de implementação por etapas (status)

| Etapa | Conteúdo | Status |
| --- | --- | --- |
| 1 | Análise e planejamento | ✅ este documento |
| 2 | Design e experiência | ✅ [04-design.md](04-design.md) |
| 3 | Estrutura, dependências, ambiente, banco | ✅ |
| 4 | Categorias, desafio diário, áudio, respostas, pontuação, estatísticas | ✅ |
| 5 | Telas, mascote, animações, estados de carregamento/erro/offline | ✅ |
| 6 | Testes automatizados e verificação manual | ✅ 124 pytest + 28 Vitest + 12 Playwright |
| 7 | Publicação | ⚠️ configuração pronta; deploy depende das suas contas (ver [05-implantacao.md](05-implantacao.md)) |

## 8. Principais riscos técnicos e soluções

| Risco | Solução adotada |
| --- | --- |
| Prévia indisponível para uma faixa/região | O sorteio verifica a disponibilidade e pula para a próxima candidata; a faixa fica marcada como indisponível. |
| Provedor de áudio fora do ar | Desafio é publicado mesmo assim; o áudio responde 503 com mensagem clara; **nenhuma tentativa é consumida**; botão "Tentar de novo". |
| URLs de prévia expiram | Guardamos o id da faixa e pedimos URL nova quando preciso; cache curto em memória. |
| Vazamento da resposta | Rotas nunca serializam a faixa antes do fim; áudio via proxy, sem metadados e sem URL externa; busca cobre o catálogo inteiro; testes automatizados de sigilo. |
| Previsão de desafios futuros | Ordem das candidatas por HMAC com segredo do servidor; desafios só são criados para o dia corrente. |
| Servidores escolhendo músicas diferentes | Restrição única (data, categoria, edição) no banco; em corrida, vale o registro existente. |
| Reenvio/duplo clique gastando tentativas | Cliente envia o número da tentativa esperada; servidor rejeita divergência; restrição única por (partida, tentativa). |
| Fuso/virada do dia | Dia definido no servidor em `America/Sao_Paulo`; cliente nunca envia data; contagem regressiva corrigida pelo relógio do servidor. |
| Autoplay bloqueado no celular | Som só começa após toque; trecho é pré-carregado para o `play()` acontecer dentro do gesto. |
| Termos de uso do Deezer | Atribuição exibida; uso pessoal/não comercial; para uso comercial, contato/licença com o Deezer ou provedor `local` com áudio licenciado. |
| Plano gratuito suspende a API | Documentado; primeira requisição após inatividade leva ~1 min. |
| Jogador anônimo limpa os dados | Limitação documentada: novo identificador, novo histórico. Evolução: contas. |
