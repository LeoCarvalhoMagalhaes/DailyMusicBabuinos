import { ChartColumn, CircleHelp, Info, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { Mascot } from '../Mascot/Mascot'
import styles from './Layout.module.css'

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className={styles.logo} aria-label="Músicas Babuínas — início">
      <Mascot variant="head" size={compact ? 34 : 42} decorative />
      <span className={styles.wordmark}>
        <span>Músicas</span>
        <span className={styles.wordmarkAccent}>Babuínas</span>
      </span>
    </Link>
  )
}

function Header() {
  const navClass = ({ isActive }: { isActive: boolean }) =>
    [styles.navLink, isActive ? styles.navActive : ''].join(' ')
  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Logo />
        <nav aria-label="Principal" className={styles.nav}>
          <NavLink to="/estatisticas" className={navClass} aria-label="Estatísticas">
            <ChartColumn size={20} aria-hidden />
            <span className={styles.navLabel} aria-hidden>Estatísticas</span>
          </NavLink>
          <NavLink to="/como-jogar" className={navClass} aria-label="Como jogar">
            <CircleHelp size={20} aria-hidden />
            <span className={styles.navLabel} aria-hidden>Como jogar</span>
          </NavLink>
          <NavLink to="/sobre" className={navClass} aria-label="Sobre">
            <Info size={20} aria-hidden />
            <span className={styles.navLabel} aria-hidden>Sobre</span>
          </NavLink>
        </nav>
      </div>
    </header>
  )
}

function OfflineBanner() {
  const online = useOnlineStatus()
  if (online) return null
  return (
    <div className={styles.offline} role="status">
      <WifiOff size={18} aria-hidden />
      Você está offline. O palco espera a conexão voltar para tocar e registrar palpites.
    </div>
  )
}

function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <p>
          <strong>Músicas Babuínas</strong> — jogo diário de adivinhação musical. Projeto
          independente, sem vínculo com gravadoras ou serviços de streaming.
        </p>
        <p className={styles.footerLinks}>
          <Link to="/como-jogar">Como jogar</Link>
          <Link to="/sobre#fontes">Fontes musicais</Link>
          <Link to="/sobre#privacidade">Privacidade</Link>
          <Link to="/sobre#termos">Termos</Link>
        </p>
      </div>
    </footer>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <a href="#conteudo" className={styles.skip}>
        Pular para o conteúdo
      </a>
      <Header />
      <OfflineBanner />
      <main id="conteudo" className={styles.main}>
        {children}
      </main>
      <Footer />
    </div>
  )
}
