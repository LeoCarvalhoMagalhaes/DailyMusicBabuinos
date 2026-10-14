import { ArrowLeft, CalendarDays } from 'lucide-react'
import { useEffect, useMemo, useRef } from 'react'
import type { CSSProperties } from 'react'
import { Link, useParams } from 'react-router'
import { Attempts } from '../components/Attempts/Attempts'
import { AudioPlayer } from '../components/AudioPlayer/AudioPlayer'
import { CategoryCard } from '../components/CategoryCard/CategoryCard'
import { DemoBanner, ErrorState, Loading } from '../components/Feedback/States'
import { GuessInput } from '../components/GuessInput/GuessInput'
import { Mascot } from '../components/Mascot/Mascot'
import { ResultPanel } from '../components/Result/ResultPanel'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import { useDaily } from '../hooks/useDaily'
import { useGame } from '../hooks/useGame'
import { useOnlineStatus } from '../hooks/useOnlineStatus'
import { useRoundEffects } from '../hooks/useRoundEffects'
import { usePlayer } from '../hooks/usePlayer'
import type { CategorySlug } from '../types/api'
import { CATEGORY_THEMES, isCategorySlug } from '../utils/categories'
import { formatChallengeDate } from '../utils/format'
import { moodForGame } from '../utils/mascot'
import { speech } from '../utils/speech'
import { NotFoundPage } from './NotFoundPage'
import styles from './ChallengePage.module.css'

function Challenge({ category }: { category: CategorySlug }) {
  const theme = CATEGORY_THEMES[category]
  const online = useOnlineStatus()
  const { ready, error: playerError, retry } = usePlayer()
  const { game, loading, error, submitting, feedback, reload, guess, skip } = useGame(category, ready)
  const daily = useDaily(ready)
  const player = useAudioPlayer(game?.id ?? null)
  const previousStatus = useRef<string | null>(null)
  const finished = !!game && game.status !== 'in_progress'

  useEffect(() => {
    document.title = `${theme.name}${game ? ` — Desafio #${game.challenge_number}` : ''} | Músicas Babuínas`
  }, [theme.name, game])

  useRoundEffects(game, feedback, player)

  useEffect(() => {
    if (game && previousStatus.current === 'in_progress' && game.status !== 'in_progress') {
      document.getElementById('resultado')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    previousStatus.current = game?.status ?? null
  }, [game])

  const mood = moodForGame(game, player.status === 'playing')
  const otherCategories = useMemo(
    () => daily.data?.categories.filter((c) => c.slug !== category) ?? [],
    [daily.data, category],
  )

  if (playerError) return <ErrorState error={playerError} onRetry={retry} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading || !game) return <Loading label={`Subindo ao palco do ${theme.name}…`} />

  return (
    <div className="page" style={{ '--accent': theme.color } as CSSProperties}>
      <div className={styles.topbar}>
        <Link to="/" className={`btn btn-ghost ${styles.back}`}>
          <ArrowLeft size={18} aria-hidden /> Categorias
        </Link>
      </div>

      <header className={styles.header}>
        <span className={styles.badge}>
          <theme.icon size={18} aria-hidden /> {theme.name}
        </span>
        <h1 className={styles.title}>Desafio #{game.challenge_number}</h1>
        <p className={styles.date}>
          <CalendarDays size={15} aria-hidden /> {game.date && formatChallengeDate(game.date)}
        </p>
      </header>

      {daily.data?.audio.demo_mode && (
        <div className={styles.demo}>
          <DemoBanner show />
        </div>
      )}

      <div className={styles.layout}>
        <div className={styles.stage}>
          <div className={styles.mascotRow}>
            <Mascot mood={finished && game.status === 'won' ? 'champion' : mood} size={150} />
            <p className={styles.bubble} aria-live="polite">
              {speech(game, feedback, player.status === 'playing')}
            </p>
          </div>
          <AudioPlayer
            player={player}
            stages={game.stages_seconds}
            unlocked={game.unlocked_stage}
            accent={theme.color}
            finished={finished}
          />
        </div>

        <div className={styles.side}>
          <Attempts guesses={game.guesses} maxAttempts={game.max_attempts} inProgress={!finished} />
          {!finished && (
            <div className={styles.input}>
              <GuessInput
                disabled={!online}
                submitting={submitting}
                canSkip={game.remaining_attempts > 0}
                lastAttempt={game.remaining_attempts === 1}
                onGuess={guess}
                onSkip={skip}
              />
            </div>
          )}
        </div>
      </div>

      {finished && (
        <div id="resultado" className={styles.result}>
          <ResultPanel
            game={game}
            onNewDay={() => {
              // Meia-noite em Brasília: a partida de ontem já acabou, então a página
              // carrega o desafio novo desta categoria.
              daily.reload()
              reload()
            }}
          />
          {otherCategories.length > 0 && (
            <section className={styles.more} aria-labelledby="outras">
              <h2 id="outras" className={styles.moreTitle}>
                Outros palcos de hoje
              </h2>
              <div className={styles.moreGrid}>
                {otherCategories.map((item) => (
                  <CategoryCard key={item.slug} item={item} maxAttempts={game.max_attempts} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

export function ChallengePage() {
  const { category } = useParams()
  if (!isCategorySlug(category)) return <NotFoundPage />
  // `key` reinicia todo o estado ao trocar de categoria.
  return <Challenge key={category} category={category} />
}
