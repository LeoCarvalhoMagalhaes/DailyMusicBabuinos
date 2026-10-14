import { ArrowDown, ArrowUp } from 'lucide-react'
import type { CSSProperties } from 'react'
import styles from '../../pages/Modes.module.css'
import type { CategorySlug } from '../../types/api'
import { CATEGORY_THEMES } from '../../utils/categories'

interface CategoryOrderProps {
  order: CategorySlug[]
  editable: boolean
  onChange?: (order: CategorySlug[]) => void
}

/** Ordem das seis categorias da partida (3 músicas em cada). O anfitrião reordena. */
export function CategoryOrder({ order, editable, onChange }: CategoryOrderProps) {
  const move = (index: number, delta: number) => {
    const next = [...order]
    const target = index + delta
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange?.(next)
  }
  return (
    <ol className={styles.list} aria-label="Ordem das categorias">
      {order.map((slug, index) => {
        const theme = CATEGORY_THEMES[slug]
        return (
          <li key={slug} className={styles.row} style={{ '--accent': theme.color } as CSSProperties}>
            <span className={styles.pill}>{index + 1}</span>
            <theme.icon size={18} aria-hidden color={theme.color} />
            <span className={styles.rowGrow}>
              {theme.name} <span className={styles.muted}>· 3 músicas</span>
            </span>
            {editable && (
              <>
                <button
                  type="button"
                  className={styles.iconBtn}
                  onClick={() => move(index, -1)}
                  disabled={index === 0}
                  aria-label={`Subir ${theme.name}`}
                >
                  <ArrowUp size={16} aria-hidden />
                </button>
                <button
                  type="button"
                  className={styles.iconBtn}
                  onClick={() => move(index, 1)}
                  disabled={index === order.length - 1}
                  aria-label={`Descer ${theme.name}`}
                >
                  <ArrowDown size={16} aria-hidden />
                </button>
              </>
            )}
          </li>
        )
      })}
    </ol>
  )
}
