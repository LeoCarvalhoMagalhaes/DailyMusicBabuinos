import { Component, useEffect } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { BrowserRouter, HashRouter, Route, Routes, useLocation } from 'react-router'
import { Layout } from './components/Layout/Layout'
import { Mascot } from './components/Mascot/Mascot'
import { PlayerProvider } from './hooks/usePlayer'
import { AboutPage } from './pages/AboutPage'
import { ChallengePage } from './pages/ChallengePage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RulesPage } from './pages/RulesPage'
import { StatsPage } from './pages/StatsPage'

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Erro na interface', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="page" style={{ display: 'grid', justifyItems: 'center', gap: 12, textAlign: 'center' }}>
        <Mascot mood="lose" size={160} decorative />
        <h1 style={{ fontSize: 26 }}>O show parou por um instante</h1>
        <p style={{ color: 'var(--text-muted)' }}>Recarregue a página para voltar ao palco.</p>
        <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
          Recarregar
        </button>
      </div>
    )
  }
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/desafio/:category" element={<ChallengePage />} />
      <Route path="/estatisticas" element={<StatsPage />} />
      <Route path="/como-jogar" element={<RulesPage />} />
      <Route path="/sobre" element={<AboutPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

// No GitHub Pages não há reescrita de rotas para o index.html: lá as rotas ficam em "#/"
// (VITE_ROUTER=hash no build). Em outros hosts, rotas normais.
const Router = import.meta.env.VITE_ROUTER === 'hash' ? HashRouter : BrowserRouter

export function App() {
  return (
    <Router>
      <ScrollToTop />
      <PlayerProvider>
        <Layout>
          <ErrorBoundary>
            <AppRoutes />
          </ErrorBoundary>
        </Layout>
      </PlayerProvider>
    </Router>
  )
}
