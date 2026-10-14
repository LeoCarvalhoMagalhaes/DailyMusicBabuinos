import { LogIn, LogOut, Plus, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { CategoryOrder } from '../components/CategoryOrder/CategoryOrder'
import { Loading } from '../components/Feedback/States'
import { Mascot } from '../components/Mascot/Mascot'
import { useAccount } from '../hooks/useAccount'
import type { UseAccount } from '../hooks/useAccount'
import { ApiError, api } from '../services/api'
import type { CategorySlug } from '../types/api'
import styles from './Modes.module.css'

const DEFAULT_ORDER: CategorySlug[] = ['rock', 'pop', 'rap', 'country', 'eletronica', 'geral']

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Algo deu errado. Tente de novo.'
}

export function AuthPanel({ auth }: { auth: UseAccount }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await auth.login(username, password)
      else await auth.register(username, password, displayName || username)
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="conta-titulo">
      <h2 id="conta-titulo" className={styles.panelTitle}>
        {mode === 'login' ? 'Entre para jogar com a galera' : 'Crie sua conta'}
      </h2>
      <div className={styles.tabs} role="tablist" aria-label="Conta">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'login'}
          className={`${styles.tab} ${mode === 'login' ? styles.tabActive : ''}`}
          onClick={() => setMode('login')}
        >
          Entrar
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'register'}
          className={`${styles.tab} ${mode === 'register' ? styles.tabActive : ''}`}
          onClick={() => setMode('register')}
        >
          Criar conta
        </button>
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.field}>
          Usuário
          <input
            className={styles.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
            minLength={3}
            maxLength={20}
          />
        </label>
        {mode === 'register' && (
          <label className={styles.field}>
            Apelido nas salas
            <input
              className={styles.input}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={24}
              placeholder="Como os outros vão te ver"
            />
          </label>
        )}
        <label className={styles.field}>
          Senha
          <input
            className={styles.input}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
            minLength={mode === 'register' ? 8 : 1}
            maxLength={128}
          />
        </label>
        {mode === 'register' && (
          <p className={styles.muted}>Usuário: 3 a 20 letras minúsculas, números ou _. Senha: 8 caracteres ou mais.</p>
        )}
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          <LogIn size={18} aria-hidden /> {mode === 'login' ? 'Entrar' : 'Criar conta e entrar'}
        </button>
      </form>
    </section>
  )
}

function Lobby({ auth }: { auth: UseAccount }) {
  const navigate = useNavigate()
  const [order, setOrder] = useState<CategorySlug[]>(DEFAULT_ORDER)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const create = async () => {
    setBusy(true)
    setError(null)
    try {
      const room = await api.createRoom(order)
      navigate(`/multiplayer/sala/${room.code}`)
    } catch (err) {
      setError(message(err))
      setBusy(false)
    }
  }

  const join = (event: FormEvent) => {
    event.preventDefault()
    const clean = code.trim().toUpperCase()
    if (clean.length >= 4) navigate(`/multiplayer/sala/${clean}`)
  }

  return (
    <>
      <div className={styles.actions} style={{ marginBottom: 16 }}>
        <p className={styles.muted}>
          Jogando como <strong>{auth.account?.display_name}</strong> (@{auth.account?.username})
        </p>
        <button type="button" className="btn btn-ghost" onClick={() => void auth.logout()}>
          <LogOut size={16} aria-hidden /> Sair da conta
        </button>
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <div className={styles.twoCols}>
        <section className={styles.panel} aria-labelledby="criar-sala">
          <h2 id="criar-sala" className={styles.panelTitle}>
            Criar sala
          </h2>
          <p className={styles.muted}>
            De 2 a 8 jogadores. A partida tem 18 músicas: 3 de cada categoria, nesta ordem.
          </p>
          <CategoryOrder order={order} editable onChange={setOrder} />
          <button type="button" className="btn btn-primary" onClick={() => void create()} disabled={busy}>
            <Plus size={18} aria-hidden /> Criar sala
          </button>
        </section>
        <section className={styles.panel} aria-labelledby="entrar-sala">
          <h2 id="entrar-sala" className={styles.panelTitle}>
            Entrar com código
          </h2>
          <form className={styles.form} onSubmit={join}>
            <label className={styles.field}>
              Código do convite
              <input
                className={`${styles.input} ${styles.code}`}
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                maxLength={12}
                autoCapitalize="characters"
                autoComplete="off"
                placeholder="ABC234"
                required
              />
            </label>
            <button type="submit" className="btn btn-secondary">
              <Users size={18} aria-hidden /> Entrar na sala
            </button>
          </form>
        </section>
      </div>
    </>
  )
}

export function MultiplayerPage() {
  const auth = useAccount()

  useEffect(() => {
    document.title = 'Multiplayer | Músicas Babuínas'
  }, [])

  return (
    <div className="page">
      <header className={styles.intro}>
        <p className="eyebrow">
          <Users size={14} aria-hidden /> Multiplayer
        </p>
        <h1 className={styles.title}>Quem tem o melhor ouvido?</h1>
        <p className={styles.lead}>
          Monte uma sala, chame até 7 amigos e disputem 18 músicas, 3 de cada categoria. Todo mundo
          ouve a mesma música ao mesmo tempo; acerto rápido vale bônus.
        </p>
      </header>
      {auth.checking ? (
        <Loading label="Conferindo sua conta…" />
      ) : auth.account ? (
        <Lobby auth={auth} />
      ) : (
        <div className={styles.twoCols}>
          <AuthPanel auth={auth} />
          <div className={styles.champion}>
            <Mascot mood="champion" size={220} />
          </div>
        </div>
      )}
    </div>
  )
}
