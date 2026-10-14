// Estados reutilizáveis: carregando, erro e aviso de modo demonstração.

import { FlaskConical, LoaderCircle, RotateCcw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { ApiError } from '../../services/api'
import { Mascot } from '../Mascot/Mascot'
import styles from './States.module.css'

export function Loading({ label = 'Afinando as guitarras…' }: { label?: string }) {
  return (
    <div className={styles.loading} role="status" aria-live="polite">
      <LoaderCircle className="spin" size={28} aria-hidden />
      <span>{label}</span>
    </div>
  )
}

interface ErrorStateProps {
  error: ApiError | null
  title?: string
  onRetry?: () => void
  children?: ReactNode
}

export function ErrorState({ error, title, onRetry, children }: ErrorStateProps) {
  const offline = error?.isNetwork
  return (
    <div className={styles.error} role="alert">
      <Mascot mood="doubt" size={140} decorative />
      <h2 className={styles.errorTitle}>
        {title ?? (offline ? 'Sem conexão com o palco' : 'Deu microfonia!')}
      </h2>
      <p className={styles.errorText}>
        {error?.message ?? 'Algo saiu do tom. Tente novamente em instantes.'}
      </p>
      <div className={styles.errorActions}>
        {onRetry && (
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            <RotateCcw size={18} aria-hidden /> Tentar de novo
          </button>
        )}
        {children}
      </div>
    </div>
  )
}

export function DemoBanner({ show }: { show: boolean }) {
  if (!show) return null
  return (
    <aside className={styles.demo} aria-label="Modo demonstração">
      <FlaskConical size={18} aria-hidden className={styles.demoIcon} />
      <p>
        <strong>Modo demonstração.</strong> Sem um provedor de áudio licenciado configurado, o
        jogo usa melodias em domínio público com arranjos sintetizados pelo próprio Músicas
        Babuínas. O catálogo real de cada categoria fica ativo com as prévias do Deezer.{' '}
        <Link to="/sobre#fontes">Saiba mais</Link>
      </p>
    </aside>
  )
}
