import { Check, ChevronRight, Play, X } from 'lucide-react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router'
import type { CategoryDailyStatus } from '../../types/api'
import { CATEGORY_THEMES } from '../../utils/categories'
import styles from './CategoryCard.module.css'

export function CategoryCard({ item, maxAttempts }: { item: CategoryDailyStatus; maxAttempts: number }) {
  const theme = CATEGORY_THEMES[item.slug]
  const Icon = theme.icon
  const done = item.status === 'won' || item.status === 'lost'
  let badge = <span className={`${styles.badge} ${styles.badgeNew}`}>Novo</span>
  let cta = 'Jogar'
  if (item.status === 'in_progress') {
    badge = (
      <span className={`${styles.badge} ${styles.badgeProgress}`}>
        {item.attempts_used}/{maxAttempts}
      </span>
    )
    cta = 'Continuar'
  } else if (item.status === 'won') {
    badge = (
      <span className={`${styles.badge} ${styles.badgeWon}`}>
        <Check size={14} aria-hidden /> {item.score} pts
      </span>
    )
    cta = 'Ver resultado'
  } else if (item.status === 'lost') {
    badge = (
      <span className={`${styles.badge} ${styles.badgeLost}`}>
        <X size={14} aria-hidden /> 0 pts
      </span>
    )
    cta = 'Ver resultado'
  }

  return (
    <Link
      to={`/desafio/${item.slug}`}
      className={[styles.card, done ? styles.done : ''].join(' ')}
      style={{ '--accent': theme.color, '--glow': theme.glow } as CSSProperties}
      aria-label={`${theme.name}: ${cta}`}
      data-testid={`category-${item.slug}`}
      data-status={item.status}
    >
      <div className={styles.top}>
        <span className={styles.icon}>
          <Icon size={24} aria-hidden />
        </span>
        {badge}
      </div>
      <h3 className={styles.name}>{theme.name}</h3>
      <p className={styles.tagline}>{theme.tagline}</p>
      <span className={styles.cta}>
        {item.status === 'not_started' ? <Play size={16} aria-hidden fill="currentColor" /> : null}
        {cta}
        <ChevronRight size={16} aria-hidden />
      </span>
    </Link>
  )
}
