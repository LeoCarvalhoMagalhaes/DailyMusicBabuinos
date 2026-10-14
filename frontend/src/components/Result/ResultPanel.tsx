import { Check, Clock, Copy, Share2 } from 'lucide-react'
import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useCountdown } from '../../hooks/useCountdown'
import type { GameState } from '../../types/api'
import { CATEGORY_THEMES } from '../../utils/categories'
import { formatCountdown } from '../../utils/format'
import { resultGrid, shareResult, shareText, siteUrl } from '../../utils/share'
import { AnswerCard } from './AnswerCard'
import styles from './ResultPanel.module.css'

interface ResultPanelProps {
  game: GameState
  serverTime?: string | null
  onNewDay?: () => void
}

export function ResultPanel({ game, serverTime, onNewDay }: ResultPanelProps) {
  const theme = CATEGORY_THEMES[game.category.slug]
  const won = game.status === 'won'
  const answer = game.answer
  const remaining = useCountdown(game.next_reset_at, serverTime, onNewDay)
  const [shareState, setShareState] = useState<'idle' | 'copied' | 'shared' | 'failed'>('idle')

  const share = async () => {
    const outcome = await shareResult(shareText(game, siteUrl()))
    if (outcome === 'cancelled') return
    setShareState(outcome)
    window.setTimeout(() => setShareState('idle'), 3000)
  }

  return (
    <section
      className={`${styles.panel} fade-up`}
      style={{ '--accent': theme.color } as CSSProperties}
      aria-labelledby="resultado-titulo"
    >
      <p className={styles.kicker}>{won ? 'Mandou bem!' : 'Não foi dessa vez'}</p>
      <h2 id="resultado-titulo" className={styles.headline}>
        {won
          ? game.attempts_used === 1
            ? 'De primeira! Ouvido absoluto.'
            : `Acertou na ${game.attempts_used}ª tentativa!`
          : 'A música era…'}
      </h2>

      {answer && <AnswerCard answer={answer} emoji={theme.emoji} />}

      <dl className={styles.numbers}>
        <div>
          <dt>Pontos</dt>
          <dd className={styles.score}>{game.score}</dd>
        </div>
        <div>
          <dt>Tentativas</dt>
          <dd>
            {game.attempts_used}/{game.max_attempts}
          </dd>
        </div>
        <div>
          <dt>Desempenho</dt>
          <dd className={styles.grid} aria-label="Resumo das tentativas">
            {resultGrid(game)}
          </dd>
        </div>
      </dl>

      <div className={styles.actions}>
        <button type="button" className="btn btn-primary" onClick={share}>
          {shareState === 'copied' ? (
            <>
              <Check size={18} aria-hidden /> Copiado!
            </>
          ) : shareState === 'shared' ? (
            <>
              <Check size={18} aria-hidden /> Compartilhado!
            </>
          ) : (
            <>
              {typeof navigator !== 'undefined' && 'share' in navigator ? (
                <Share2 size={18} aria-hidden />
              ) : (
                <Copy size={18} aria-hidden />
              )}
              Compartilhar resultado
            </>
          )}
        </button>
        <p className={styles.shareNote} role="status" aria-live="polite">
          {shareState === 'failed'
            ? 'Não deu para copiar automaticamente. Selecione o texto e copie manualmente.'
            : 'O texto não revela a música para quem ainda não jogou.'}
        </p>
      </div>

      <div className={styles.next}>
        <Clock size={18} aria-hidden />
        <span>
          Próximo desafio em <strong className={styles.countdown}>{formatCountdown(remaining)}</strong>
        </span>
      </div>
    </section>
  )
}
