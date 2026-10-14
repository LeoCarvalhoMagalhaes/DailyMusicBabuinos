import { CalendarDays, Flame, Play, Trophy } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { CategoryCard } from '../components/CategoryCard/CategoryCard'
import { DemoBanner, ErrorState, Loading } from '../components/Feedback/States'
import { Mascot } from '../components/Mascot/Mascot'
import { useCountdown } from '../hooks/useCountdown'
import { useDaily } from '../hooks/useDaily'
import { usePlayer } from '../hooks/usePlayer'
import { api } from '../services/api'
import { STORAGE_KEYS, readJSON, writeJSON } from '../services/storage'
import type { Statistics } from '../types/api'
import { formatChallengeDate, formatCountdown } from '../utils/format'
import styles from './HomePage.module.css'

function useStatsSummary(enabled: boolean, refreshKey: string | undefined) {
  const [stats, setStats] = useState<Statistics | null>(() => readJSON(STORAGE_KEYS.stats))
  useEffect(() => {
    if (!enabled) return
    api
      .statistics()
      .then((data) => {
        setStats(data)
        writeJSON(STORAGE_KEYS.stats, data)
      })
      .catch(() => {
        /* mantém o cache local, se houver */
      })
  }, [enabled, refreshKey])
  return stats
}

export function HomePage() {
  const { ready, error: playerError, retry } = usePlayer()
  const { data, error, loading, reload } = useDaily(ready)
  const statusKey = data?.categories.map((c) => c.status).join(',')
  const stats = useStatsSummary(ready, statusKey)
  const remaining = useCountdown(data?.next_reset_at ?? null, data?.server_time, reload)

  useEffect(() => {
    document.title = 'Músicas Babuínas — desafio musical diário'
  }, [])

  if (playerError) return <ErrorState error={playerError} onRetry={retry} />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />

  const done = data?.categories.filter((c) => c.status === 'won' || c.status === 'lost').length ?? 0
  const todayPoints = data?.categories.reduce((sum, c) => sum + c.score, 0) ?? 0
  const next = data?.categories.find((c) => c.status === 'in_progress') ??
    data?.categories.find((c) => c.status === 'not_started')
  const allDone = data && done === data.categories.length

  return (
    <div className="page">
      <section className={styles.hero}>
        <div className={styles.heroText}>
          <p className="eyebrow">
            <CalendarDays size={14} aria-hidden className={styles.inlineIcon} />
            {data ? `Desafio #${data.challenge_number} · ${formatChallengeDate(data.date)}` : 'Desafio de hoje'}
          </p>
          <h1 className={styles.title}>
            Ouviu? <span className={styles.titleAccent}>Adivinha!</span>
          </h1>
          <p className={styles.lead}>
            Um trecho curtinho, seis chances e um babuíno roqueiro torcendo por você. A cada erro, a
            música toca um pouco mais. Seis categorias, um desafio novo por dia em cada uma.
          </p>
          <div className={styles.heroActions}>
            {next && (
              <Link to={`/desafio/${next.slug}`} className="btn btn-primary">
                <Play size={18} aria-hidden fill="currentColor" />
                {next.status === 'in_progress' ? `Continuar ${next.name}` : `Jogar ${next.name}`}
              </Link>
            )}
            <Link to="/como-jogar" className="btn btn-secondary">
              Como jogar
            </Link>
          </div>
        </div>
        <div className={styles.heroArt}>
          <div className={styles.spotlight} aria-hidden />
          <Mascot mood={allDone ? 'champion' : 'idle'} size={250} />
        </div>
      </section>

      <section className={styles.summary} aria-label="Resumo do dia">
        <div className={styles.summaryItem}>
          <Flame size={20} aria-hidden className={styles.flame} />
          <div>
            <p className={styles.summaryValue}>{stats?.overall.current_streak ?? 0}</p>
            <p className={styles.summaryLabel}>dias seguidos</p>
          </div>
        </div>
        <div className={styles.summaryItem}>
          <Trophy size={20} aria-hidden className={styles.trophy} />
          <div>
            <p className={styles.summaryValue}>{stats?.overall.best_streak ?? 0}</p>
            <p className={styles.summaryLabel}>melhor sequência</p>
          </div>
        </div>
        <div className={styles.summaryItem}>
          <div className={styles.ring} aria-hidden>
            {done}/6
          </div>
          <div>
            <p className={styles.summaryValue}>{todayPoints}</p>
            <p className={styles.summaryLabel}>pontos hoje</p>
          </div>
        </div>
        <div className={styles.summaryItem}>
          <div>
            <p className={`${styles.summaryValue} ${styles.mono}`}>{formatCountdown(remaining)}</p>
            <p className={styles.summaryLabel}>para os próximos desafios</p>
          </div>
        </div>
      </section>

      {data && (
        <div className={styles.demo}>
          <DemoBanner show={data.audio.demo_mode} />
        </div>
      )}

      <section aria-labelledby="categorias">
        <div className={styles.sectionHead}>
          <h2 id="categorias" className={styles.sectionTitle}>
            Escolha seu palco
          </h2>
          {allDone && <p className={styles.allDone}>Você zerou o dia! Volte amanhã para o bis. 🤘</p>}
        </div>
        {loading && !data ? (
          <Loading label="Montando o palco…" />
        ) : (
          <div className={styles.grid}>
            {data?.categories.map((item) => (
              <CategoryCard key={item.slug} item={item} maxAttempts={data.rules.max_attempts} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
