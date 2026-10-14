import { ArrowLeft, ChevronRight, Infinity as InfinityIcon, RotateCcw, SkipForward } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link, useParams } from 'react-router'
import { Attempts } from '../components/Attempts/Attempts'
import { AudioPlayer } from '../components/AudioPlayer/AudioPlayer'
import { ErrorState, Loading } from '../components/Feedback/States'
import { GuessInput } from '../components/GuessInput/GuessInput'
import { Mascot } from '../components/Mascot/Mascot'
import { AnswerCard } from '../components/Result/AnswerCard'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import { useEndless } from '../hooks/useEndless'
import { useOnlineStatus } from '../hooks/useOnlineStatus'
import { usePlayer } from '../hooks/usePlayer'
import { useRoundEffects } from '../hooks/useRoundEffects'
import { api } from '../services/api'
import type { CategorySlug, EndlessStats } from '../types/api'
import { CATEGORY_THEMES, isCategorySlug } from '../utils/categories'
import { moodForGame } from '../utils/mascot'
import { speech } from '../utils/speech'
import { NotFoundPage } from './NotFoundPage'
import challenge from './ChallengePage.module.css'
import styles from './Modes.module.css'

const ORDER: CategorySlug[] = ['rock', 'pop', 'rap', 'country', 'eletronica', 'geral']

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** Escolha de categoria e estatísticas do modo ilimitado. */
export function EndlessHubPage() {
  const { ready, error: playerError, retry } = usePlayer()
  const [stats, setStats] = useState<EndlessStats | null>(null)

  useEffect(() => {
    document.title = 'Modo Ilimitado | Músicas Babuínas'
  }, [])

  useEffect(() => {
    if (!ready) return
    api
      .endlessStats()
      .then(setStats)
      .catch(() => {
        /* as estatísticas são opcionais nesta tela */
      })
  }, [ready])

  if (playerError) return <ErrorState error={playerError} onRetry={retry} />
  const byCategory = new Map(stats?.categories.map((c) => [c.category, c]))
  const overall = stats?.overall

  return (
    <div className="page">
      <header className={styles.intro}>
        <p className="eyebrow">
          <InfinityIcon size={14} aria-hidden /> Modo Ilimitado
        </p>
        <h1 className={styles.title}>Jogue quanto quiser</h1>
        <p className={styles.lead}>
          Rodadas solo sem fim, com as mesmas regras do desafio diário: seis tentativas, trechos que
          crescem a cada erro e a mesma pontuação. As músicas não se repetem tão cedo e o modo não
          mexe no seu desafio diário.
        </p>
      </header>

      {overall && overall.rounds > 0 && (
        <section className={styles.stats} aria-label="Seu desempenho no modo ilimitado">
          <div className={styles.stat}>
            <p className={styles.statValue}>{overall.rounds}</p>
            <p className={styles.statLabel}>rodadas</p>
          </div>
          <div className={styles.stat}>
            <p className={styles.statValue}>{percent(overall.win_rate)}</p>
            <p className={styles.statLabel}>de acerto</p>
          </div>
          <div className={styles.stat}>
            <p className={styles.statValue}>{overall.total_score}</p>
            <p className={styles.statLabel}>pontos</p>
          </div>
          <div className={styles.stat}>
            <p className={styles.statValue}>{overall.best_streak}</p>
            <p className={styles.statLabel}>melhor sequência</p>
          </div>
        </section>
      )}

      <section aria-labelledby="ilimitado-categorias" className={styles.section}>
        <h2 id="ilimitado-categorias" className={styles.sectionTitle}>
          Escolha a categoria
        </h2>
        <div className={styles.tiles}>
          {ORDER.map((slug) => {
            const theme = CATEGORY_THEMES[slug]
            const item = byCategory.get(slug)
            return (
              <Link
                key={slug}
                to={`/ilimitado/${slug}`}
                className={styles.tile}
                style={{ '--accent': theme.color } as CSSProperties}
                data-testid={`endless-${slug}`}
              >
                <span className={styles.tileHead}>
                  <theme.icon size={20} aria-hidden /> {theme.name}
                  <ChevronRight size={18} aria-hidden style={{ marginLeft: 'auto' }} />
                </span>
                <span className={styles.tileStats}>
                  {item && item.rounds > 0
                    ? `${item.rounds} rodadas · ${percent(item.win_rate)} de acerto · sequência ${item.current_streak} (melhor ${item.best_streak})`
                    : theme.tagline}
                </span>
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}

function EndlessGame({ category }: { category: CategorySlug }) {
  const theme = CATEGORY_THEMES[category]
  const online = useOnlineStatus()
  const { ready, error: playerError, retry } = usePlayer()
  const endless = useEndless(category, ready)
  const { game, run, loading, error, feedback, submitting } = endless
  const player = useAudioPlayer(game?.id ?? null)
  const finished = !!game && game.status !== 'in_progress'
  const nextButton = useRef<HTMLButtonElement>(null)
  useRoundEffects(game, feedback, player)

  useEffect(() => {
    document.title = `${theme.name} — Modo Ilimitado | Músicas Babuínas`
  }, [theme.name])

  useEffect(() => {
    if (finished) nextButton.current?.focus({ preventScroll: true })
  }, [finished])

  const mood = moodForGame(game, player.status === 'playing')
  const roundNumber = useMemo(() => (run ? run.rounds + (finished ? 0 : 1) : 1), [run, finished])

  if (playerError) return <ErrorState error={playerError} onRetry={retry} />
  if (error) return <ErrorState error={error} onRetry={endless.next} />
  if (loading || !game) return <Loading label={`Sorteando uma música de ${theme.name}…`} />

  return (
    <div className="page" style={{ '--accent': theme.color } as CSSProperties}>
      <div className={challenge.topbar}>
        <Link to="/ilimitado" className={`btn btn-ghost ${challenge.back}`}>
          <ArrowLeft size={18} aria-hidden /> Categorias
        </Link>
      </div>

      <header className={challenge.header}>
        <span className={challenge.badge}>
          <theme.icon size={18} aria-hidden /> {theme.name} · Ilimitado
        </span>
        <h1 className={challenge.title}>Rodada {roundNumber}</h1>
      </header>

      <section className={styles.stats} aria-label="Placar da sessão">
        <div className={styles.stat}>
          <p className={styles.statValue} data-testid="session-score">{run?.score ?? 0}</p>
          <p className={styles.statLabel}>pontos na sessão</p>
        </div>
        <div className={styles.stat}>
          <p className={styles.statValue} data-testid="session-wins">{run?.wins ?? 0}</p>
          <p className={styles.statLabel}>músicas acertadas</p>
        </div>
        <div className={styles.stat}>
          <p className={styles.statValue} data-testid="session-streak">{run?.current_streak ?? 0}</p>
          <p className={styles.statLabel}>acertos seguidos</p>
        </div>
        <div className={styles.stat}>
          <p className={styles.statValue}>{run?.best_streak ?? 0}</p>
          <p className={styles.statLabel}>melhor sequência</p>
        </div>
      </section>

      <div className={challenge.layout}>
        <div className={challenge.stage}>
          <div className={challenge.mascotRow}>
            <Mascot mood={finished && game.status === 'won' ? 'champion' : mood} size={150} />
            <p className={challenge.bubble} aria-live="polite">
              {speech(game, feedback, player.status === 'playing', 'Essa escapou! Bora pra próxima?')}
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

        <div className={challenge.side}>
          <Attempts guesses={game.guesses} maxAttempts={game.max_attempts} inProgress={!finished} />
          {!finished && (
            <div className={challenge.input}>
              <GuessInput
                disabled={!online}
                submitting={submitting}
                canSkip={game.remaining_attempts > 0}
                lastAttempt={game.remaining_attempts === 1}
                onGuess={endless.guess}
                onSkip={endless.skip}
              />
            </div>
          )}
        </div>
      </div>

      {finished && (
        <section className={`${styles.panel} ${challenge.result} fade-up`} aria-labelledby="rodada-resultado">
          <h2 id="rodada-resultado" className={styles.panelTitle}>
            {game.status === 'won'
              ? `Acertou na ${game.attempts_used}ª tentativa! +${game.score} pontos`
              : 'A música era…'}
          </h2>
          {game.answer && <AnswerCard answer={game.answer} emoji={theme.emoji} />}
          <div className={styles.actions}>
            <button ref={nextButton} type="button" className="btn btn-primary" onClick={() => void endless.next()}>
              <SkipForward size={18} aria-hidden /> Próxima música
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => void endless.newSession()}>
              <RotateCcw size={18} aria-hidden /> Nova sessão
            </button>
          </div>
        </section>
      )}
    </div>
  )
}

export function EndlessPlayPage() {
  const { category } = useParams()
  if (!isCategorySlug(category)) return <NotFoundPage />
  return <EndlessGame key={category} category={category} />
}
