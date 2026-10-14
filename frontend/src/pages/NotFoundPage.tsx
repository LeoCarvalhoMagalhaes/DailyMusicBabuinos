import { useEffect } from 'react'
import { Link } from 'react-router'
import { Mascot } from '../components/Mascot/Mascot'

export function NotFoundPage() {
  useEffect(() => {
    document.title = 'Página não encontrada | Músicas Babuínas'
  }, [])
  return (
    <div className="page" style={{ display: 'grid', justifyItems: 'center', gap: 14, textAlign: 'center' }}>
      <Mascot mood="lose" size={180} decorative />
      <h1 style={{ fontSize: 30 }}>404 — essa faixa não existe</h1>
      <p style={{ color: 'var(--text-muted)' }}>O babuíno procurou no setlist inteiro e não achou.</p>
      <Link to="/" className="btn btn-primary">
        Voltar para o palco
      </Link>
    </div>
  )
}
