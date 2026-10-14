import { Check, Flame, Minus, Trophy, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router'
import { ErrorState, Loading } from '../components/Feedback/States'
import { Mascot } from '../components/Mascot/Mascot'
import { usePlayer } from '../hooks/usePlayer'
import { ApiError, api } from '../services/api'
import { STORAGE_KEYS, readJSON, writeJSON } from '../services/storage'
import type { CategorySlug, HistoryItem, Statistics, StatsBlock } from '../types/api'
import { CATEGORY_THEMES } from '../utils/categories'
import { formatPercent, formatShortDate } from '../utils/format'
import styles from './StatsPage.module.css'

const PAGE = 20

function Tiles({ block }: { block: StatsBlock }) {
  const items = [
    { label: 'Jogos', value: block.games_played },
    { label: 'Vitórias', value: block.wins },
    { label: 'Taxa de acerto', value: formatPercent(block.win_rate) },
    { label: 'Pontos', value: block.total_score },
    { label: 'Média por jogo', value: block.average_score.toLocaleString('pt-BR') },
    { label: 'Sequência atual', value: block.current_streak, icon: <Flame size={16} aria-hidden /> },
    { label: 'Melhor sequência', value: block.best_streak, icon: <Trophy size={16} aria-hidden /> },
  ]
  return (
    <dl className={styles.tiles}>
      {items.map((item) => (
        <div key={item.label} className={styles.tile}>
          <dt>{item.label}</dt>
          <dd>
            {item.icon}
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function Distribution({ block }: { block: StatsBlock }) {
  const max = Math.max(1, ...block.distribution)
  const labels = block.distribution.map((_, i) =>
    i === block.distribution.length - 1 ? 'X' : String(i + 1),
  )
  return (
    <figure className={styles.chart}>
      <figcaption className={styles.chartTitle}>Acertos por tentativa</figcaption>
      <ol className={styles.bars}>
        {block.distribution.map((count, i) => {
          const isLoss = i === block.distribution.length - 1
          return (
            <li key={labels[i]} className={styles.barRow}>
              <span className={styles.barLabel} aria-hidden>
                {labels[i]}
              </span>
              <span className={styles.barTrack}>
                <span
                  className={[styles.bar, isLoss ? styles.barLoss : ''].join(' ')}
                  style={{ width: `${Math.max(count > 0 ? 8 : 0, (count / max) * 100)}%` }}
                />
              </span>
              <span className={styles.barValue}>
                {count}
                <span className="visually-hidden">
                  {isLoss ? ' derrotas' : ` vitórias na tentativa ${i + 1}`}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
    </figure>
  )
}

function CategoryStats({ block }: { block: StatsBlock }) {
  const theme = CATEGORY_THEMES[block.category as CategorySlug]
  return (
    <article className={styles.catCard} style={{ '--accent': theme.color } as CSSProperties}>
      <h3 className={styles.catName}>
        <theme.icon size={18} aria-hidden /> {theme.name}
      </h3>
      <p className={styles.catLine}>
        <strong>{block.games_played}</strong> {block.games_played === 1 ? 'jogo' : 'jogos'} ·{' '}
        <strong>{formatPercent(block.win_rate)}</strong> de acerto
      </p>
      <p className={styles.catLine}>
        <strong>{block.total_score}</strong> pts · média <strong>{block.average_score.toLocaleString('pt-BR')}</strong>
      </p>
      <p className={styles.catLine}>
        Sequência <strong>{block.current_streak}</strong> (melhor {block.best_streak})
      </p>
    </article>
  )
}

function HistoryRow({ item }: { item: HistoryItem }) {
  const theme = CATEGORY_THEMES[item.category.slug]
  const icon =
    item.status === 'won' ? <Check size={16} aria-label="Vitória" /> : item.status === 'lost' ? <X size={16} aria-label="Derrota" /> : <Minus size={16} aria-label="Em andamento" />
  return (
    <li className={[styles.historyRow, styles[item.status]].join(' ')}>
      <span className={styles.historyIcon}>{icon}</span>
      <span className={styles.historyMain}>
        <span className={styles.historyTitle}>
          {item.answer ? `${item.answer.title} — ${item.answer.artist}` : 'Partida em andamento'}
        </span>
        <span className={styles.historyMeta}>
          <span style={{ color: theme.color }}>{theme.name}</span> · #{item.challenge_number} ·{' '}
          {formatShortDate(item.date)}
        </span>
      </span>
      <span className={styles.historyScore}>
        {item.status === 'in_progress' ? (
          <Link to={`/desafio/${item.category.slug}`}>Continuar</Link>
        ) : (
          <>
            <strong>{item.score}</strong> pts
            <span className={styles.historyAttempts}>
              {item.attempts_used} {item.attempts_used === 1 ? 'tentativa' : 'tentativas'}
            </span>
          </>
        )}
      </span>
    </li>
  )
}

export function StatsPage() {
  const { ready, error: playerError, retry } = usePlayer()
  const [stats, setStats] = useState<Statistics | null>(() => readJSON(STORAGE_KEYS.stats))
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [tab, setTab] = useState<'all' | CategorySlug>('all')

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([api.statistics(), api.history(PAGE, 0)])
      .then(([s, h]) => {
        setStats(s)
        writeJSON(STORAGE_KEYS.stats, s)
        setHistory(h.items)
        setTotal(h.total)
      })
      .catch((err: ApiError) => setError(err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    document.title = 'Estatísticas | Músicas Babuínas'
    if (ready) load()
  }, [ready, load])

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      const page = await api.history(PAGE, history.length)
      setHistory((items) => [...items, ...page.items])
      setTotal(page.total)
    } finally {
      setLoadingMore(false)
    }
  }

  if (playerError) return <ErrorState error={playerError} onRetry={retry} />
  if (error && !stats) return <ErrorState error={error} onRetry={load} />
  if (!stats) return <Loading label="Somando os pontos…" />

  const block = tab === 'all' ? stats.overall : stats.categories.find((c) => c.category === tab)!

  return (
    <div className="page">
      <header className={styles.header}>
        <div>
          <p className="eyebrow">Seu desempenho</p>
          <h1 className={styles.title}>Estatísticas</h1>
          <p className={styles.lead}>
            Seus números ficam salvos neste aparelho e no servidor, ligados a um identificador
            anônimo. {error && <span className={styles.stale}>Mostrando a última versão salva.</span>}
          </p>
        </div>
        <Mascot mood={stats.overall.wins > 0 ? 'champion' : 'idle'} size={120} decorative />
      </header>

      <div className={styles.tabs} role="tablist" aria-label="Filtrar por categoria">
        {(['all', 'rock', 'pop', 'rap', 'country', 'eletronica', 'geral'] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={[styles.tab, tab === key ? styles.tabActive : ''].join(' ')}
            onClick={() => setTab(key)}
          >
            {key === 'all' ? 'Todas' : CATEGORY_THEMES[key].name}
          </button>
        ))}
      </div>

      <section className={styles.overview} aria-label="Resumo">
        <Tiles block={block} />
        <Distribution block={block} />
      </section>

      {tab === 'all' && (
        <section className={styles.section} aria-labelledby="por-genero">
          <h2 id="por-genero" className={styles.sectionTitle}>
            Por gênero
          </h2>
          <div className={styles.catGrid}>
            {stats.categories.map((c) => (
              <CategoryStats key={c.category} block={c} />
            ))}
          </div>
        </section>
      )}

      <section className={styles.section} aria-labelledby="historico">
        <h2 id="historico" className={styles.sectionTitle}>
          Histórico
        </h2>
        {loading && history.length === 0 ? (
          <Loading label="Buscando seus shows…" />
        ) : history.length === 0 ? (
          <p className={styles.empty}>
            Nenhuma partida ainda. <Link to="/">Escolha uma categoria</Link> e comece sua turnê!
          </p>
        ) : (
          <>
            <ul className={styles.history}>
              {history.map((item) => (
                <HistoryRow key={item.game_id} item={item} />
              ))}
            </ul>
            {history.length < total && (
              <button type="button" className="btn btn-secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? 'Carregando…' : 'Carregar mais'}
              </button>
            )}
          </>
        )}
      </section>
    </div>
  )
}
