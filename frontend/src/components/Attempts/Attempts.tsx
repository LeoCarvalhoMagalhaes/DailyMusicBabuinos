import { Check, SkipForward, X } from 'lucide-react'
import type { GuessEntry } from '../../types/api'
import styles from './Attempts.module.css'

interface AttemptsProps {
  guesses: GuessEntry[]
  maxAttempts: number
  inProgress: boolean
}

/** Lista das 6 tentativas: o que foi tentado, o que foi pulado e as restantes. */
export function Attempts({ guesses, maxAttempts, inProgress }: AttemptsProps) {
  const remaining = maxAttempts - guesses.length
  return (
    <section aria-label="Tentativas">
      <div className={styles.header}>
        <h2 className={styles.title}>Tentativas</h2>
        <p className={styles.counter} aria-live="polite">
          {inProgress ? (
            <>
              <strong>{remaining}</strong> {remaining === 1 ? 'restante' : 'restantes'}
            </>
          ) : (
            `${guesses.length}/${maxAttempts} usadas`
          )}
        </p>
      </div>
      <ol className={styles.list}>
        {Array.from({ length: maxAttempts }, (_, i) => {
          const guess = guesses[i]
          const current = inProgress && i === guesses.length
          let cls = styles.empty
          let content = current ? 'Sua vez — ouça e responda' : ''
          let icon = null
          if (guess?.correct) {
            cls = styles.correct
            content = guess.text
            icon = <Check size={18} aria-label="Acertou" />
          } else if (guess?.skipped) {
            cls = styles.skipped
            content = 'Pulou'
            icon = <SkipForward size={16} aria-label="Pulou" />
          } else if (guess) {
            cls = styles.wrong
            content = guess.text
            icon = <X size={18} aria-label="Errou" />
          }
          return (
            <li key={i} className={[styles.item, cls, current ? styles.current : ''].join(' ')}>
              <span className={styles.number}>{i + 1}</span>
              <span className={styles.text}>{content}</span>
              {icon && <span className={styles.icon}>{icon}</span>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
