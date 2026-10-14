# Áudio, licenciamento e catálogo

## Provedores de áudio

A camada `backend/app/audio` expõe a interface `AudioProvider`:

```python
class AudioProvider(ABC):
    def check_availability(self, track) -> bool: ...          # resolve id externo, capa, link
    def get_clip(self, track, seconds, category=None) -> AudioClip: ...  # primeiros N segundos
    def metadata(self, track) -> TrackMetadata: ...            # capa/link/atribuição pós-jogo
```

Selecionado por `AUDIO_PROVIDER`:

| Valor | Catálogo | Fonte | Precisa de rede/credenciais |
| --- | --- | --- | --- |
| `demo` (padrão) | edição `demo` (27 melodias) | síntese própria de composições em domínio público | não |
| `deezer` | edição `main` (6 × 100) | prévias de 30 s da API pública do Deezer | rede; sem chave de API |
| `local` | edição `main` | arquivos `AUDIO_LOCAL_DIR/<slug>.mp3` ou `.wav` licenciados por você | não |

Trocar de provedor não muda nenhuma regra do jogo.

### Deezer — o que foi verificado

- A API pública (`https://api.deezer.com`) devolve, para cada faixa, um campo `preview` com
  uma prévia MP3 de cerca de 30 segundos. A documentação para desenvolvedores do Deezer
  descreve prévias de 30 s para usuários não logados e não fornece o arquivo completo pela
  API ([FAQ para desenvolvedores](https://support.deezer.com/hc/en-gb/articles/360011538897-Deezer-FAQs-For-Developers)).
- Termos para desenvolvedores: acesso gratuito para **páginas e aplicações pessoais**, com
  atribuição; os termos podem mudar a qualquer momento
  ([termos](https://developers.deezer.com/termsofuse)). **Antes de publicar com fins
  comerciais (anúncios, assinatura), contate o Deezer ou use o provedor `local` com áudio
  licenciado.**
- Cota: uma fonte de terceiros cita 50 requisições a cada 5 s por IP (não confirmado na
  documentação oficial). O jogo faz poucas chamadas: uma busca por faixa sorteada, uma
  consulta por download de prévia, e as prévias ficam em cache em memória por 10 min.
- URLs de prévia são assinadas e expiram. Por isso guardamos o `id` da faixa e pedimos a URL
  de novo quando necessário.
- Nem toda faixa tem prévia em todas as regiões. O sorteio verifica e pula as indisponíveis.
- **Não foi possível testar contra o Deezer real neste ambiente** (acesso bloqueado). O
  provedor foi testado com respostas simuladas fiéis ao formato da API. Valide no primeiro
  deploy com `python -m app.cli check-audio --limit 20`.

### Outras fontes avaliadas

- **Spotify Web API:** o campo `preview_url` deixou de ser preenchido para apps criados (ou em
  modo de desenvolvimento) a partir de 27/11/2024, segundo a comunidade oficial de
  desenvolvedores. Descartado.
- **iTunes Search API (Apple):** oferece prévias, mas a documentação não pôde ser consultada
  deste ambiente e o uso é condicionado a fins promocionais com link para a loja. Pode virar
  um `ItunesProvider` com a mesma interface.
- **YouTube e afins:** extrair áudio viola os termos de uso. Não usado.
- **Catálogos licenciados (bibliotecas de música para criadores):** juridicamente simples,
  mas raramente contêm os sucessos que tornam o jogo divertido. Servem via provedor `local`.

### Como o trecho é entregue

1. O navegador pede `/api/games/{id}/audio?stage=N` com o token.
2. A API confere se o estágio N está liberado para aquela partida.
3. O provedor obtém o áudio (prévia em cache, arquivo local ou síntese).
4. `app/audio/mp3.py` pula as tags ID3v2, descarta o quadro Xing/Info/VBRI (que informaria a
   duração total) e copia somente os quadros MPEG necessários para N segundos. A tag ID3v1 do
   final nunca é incluída. Para WAV, `app/audio/wav.py` reconstrói um cabeçalho mínimo (sem
   blocos de metadados) e aplica um fade-out de 25 ms.
5. Resposta com `Cache-Control: no-store`, `X-Clip-Duration` e nenhum nome de arquivo.

Assim, o jogador baixa no máximo o que já pode ouvir, e nada na URL, no arquivo ou nos
cabeçalhos identifica a música.

### Modo demonstração

- Ativo por padrão, claramente sinalizado na interface (faixa amarela na home e no desafio, e
  na página Sobre).
- 27 composições em domínio público (Beethoven, Bach, Mozart, Grieg, Pachelbel, Brahms,
  Joplin, Foster e canções tradicionais), transcritas em `app/data/scores/melodies.json`.
- `app/audio/synth.py` gera arranjos diferentes por categoria (rock com guitarra distorcida,
  rap com batida boom bap e swing, country com "boom-chick", eletrônica com bumbo quatro por
  quatro e sidechain etc.). Todo o áudio é produzido pelo código: não há gravação de terceiros.
- O catálogo demo **não** é o catálogo definitivo do jogo.

## Catálogo principal

- Arquivos: `backend/app/data/catalog/{rock,pop,rap,country,eletronica,geral}.json`.
- 100 faixas por categoria, 545 faixas únicas (a categoria Geral compartilha 55 faixas com as
  demais, como pede o enunciado).
- **Metodologia:** curadoria editorial (não é ranking oficial). Critérios registrados em cada
  arquivo: faixas amplamente reconhecíveis, presença recorrente em paradas, listas editoriais
  e catálogos de streaming, diversidade de décadas e subgêneros, no máximo 3 faixas por artista
  e inclusão de produção nacional (na categoria Country, a vertente brasileira é o sertanejo).
- **Sem posições inventadas:** `rank` é nulo em fontes `editorial`, e o carregador rejeita
  posição em fonte que não seja `chart`.

### Formato

```json
{
  "edition": "main",
  "category": "rock",
  "source": {
    "id": "editorial-rock-2026-10",
    "name": "Curadoria editorial Músicas Babuínas — Rock",
    "kind": "editorial",
    "url": null,
    "retrieved_on": "2026-10-14",
    "methodology": "…"
  },
  "tracks": [
    {"title": "Sweet Child O' Mine", "artist": "Guns N' Roses",
     "genres": ["hard rock"], "aliases": ["Sweet Child of Mine"]}
  ]
}
```

Campos opcionais por faixa: `genres`, `aliases`, `rank` (só com fonte `chart`), `slug`,
`categories` (em vez de `category` no arquivo), `audio_ref`, `license`.

### Como atualizar o catálogo sem reescrever o jogo

1. Edite ou adicione arquivos JSON (por exemplo, um `rock.json` com fonte `chart`, URL do
   ranking e data da consulta, e `rank` em cada faixa).
2. Reinicie a API (`AUTO_SYNC_CATALOG=true`) ou rode `python -m app.cli sync-catalog`.
3. A sincronização insere/atualiza faixas pela chave estável `slug` (`artista--titulo`),
   nunca apaga faixas usadas em desafios antigos e marca como inativas as que saíram da lista.
4. Opcional: `python -m app.cli check-audio --limit 100` resolve os ids no Deezer e marca as
   faixas sem prévia.
5. Desafios já publicados não mudam; o sorteio dos próximos dias passa a considerar a lista nova.

### Validação de respostas

- Resposta principal: **título**. Aliases cobrem variações conhecidas (ex.: "Sweet Child of
  Mine", "Parabéns pra Você").
- Normalização: remove acentos, maiúsculas, pontuação, `feat.`, sufixos como
  "- Remastered 2011", artigos iniciais (the/a/o/os/as) e aceita o título com ou sem o trecho
  entre parênteses.
- Tolerância a erros de digitação: distância de edição 1 (títulos com 5+ caracteres) ou
  2 (12+), **exceto** se o palpite for exatamente outra música do catálogo.
- O artista não é aceito como resposta.
