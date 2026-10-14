import { Check, Copy, Crown, DoorOpen, Play, Radio, Timer, Trophy, Wifi, WifiOff, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Attempts } from '../components/Attempts/Attempts'
import { AudioPlayer } from '../components/AudioPlayer/AudioPlayer'
import { CategoryOrder } from '../components/CategoryOrder/CategoryOrder'
import { ErrorState, Loading } from '../components/Feedback/States'
import { GuessInput } from '../components/GuessInput/GuessInput'
import { Mascot } from '../components/Mascot/Mascot'
import { AnswerCard } from '../components/Result/AnswerCard'
import { useAccount } from '../hooks/useAccount'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import { useCountdown } from '../hooks/useCountdown'
import { useOnlineStatus } from '../hooks/useOnlineStatus'
import { useRoom } from '../hooks/useRoom'
import type { Connection, UseRoom } from '../hooks/useRoom'
import { useRoundEffects } from '../hooks/useRoundEffects'
import { api } from '../services/api'
import type { MatchState, RoomState } from '../types/api'
import { CATEGORY_THEMES } from '../utils/categories'
import { moodForGame } from '../utils/mascot'
import { speech } from '../utils/speech'
import { AuthPanel } from './MultiplayerPage'
import challenge from './ChallengePage.module.css'
import styles from './Modes.module.css'

function ConnectionBadge({ connection }: { connection: Connection }) {
  const label =
    connection === 'live' ? 'Ao vivo' : connection === 'polling' ? 'Reconectando…' : 'Conectando…'
  return (
    <span className={`${styles.pill} ${connection === 'live' ? styles.pillOk : ''}`} role="status">
      {connection === 'live' ? <Wifi size={12} aria-hidden /> : <WifiOff size={12} aria-hidden />} {label}
    </span>
  )
}

function seconds(ms: number): string {
  return `${Math.ceil(ms / 1000)}s`
}

// ------------------------------------------------------------- placar final

export function FinalResults({ match, me }: { match: MatchState; me: string }) {
  const winners = match.scoreboard.filter((s) => match.winner_ids.includes(s.account_id))
  const order = match.scoreboard[0]?.per_category.map((c) => c.category) ?? []
  return (
    <section className={`${styles.panel} fade-up`} aria-labelledby="classificacao">
      {match.status === 'finished' ? (
        <div className={styles.champion}>
          <Mascot mood="champion" size={180} />
          <p className="eyebrow">
            <Trophy size={14} aria-hidden /> {winners.length > 1 ? 'Empate no topo!' : 'Campeão da noite'}
          </p>
          <p className={styles.championName} data-testid="winner">
            {winners.map((w) => w.display_name).join(' & ')}
          </p>
          <p className={styles.muted}>
            {winners.some((w) => w.account_id === me)
              ? 'Você mandou muito! O Babuíno do Rock faz o sinal do rock pra você. 🤘'
              : 'Que show! Bora revanche?'}
          </p>
        </div>
      ) : (
        <p className={styles.muted}>A partida foi encerrada antes do fim (todos saíram ou ficaram inativos).</p>
      )}
      <h2 id="classificacao" className={styles.panelTitle}>
        Classificação final
      </h2>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Jogador</th>
              <th scope="col" className={styles.num}>
                Pontos
              </th>
              <th scope="col" className={styles.num}>
                Acertos
              </th>
              {order.map((slug) => (
                <th key={slug} scope="col" className={styles.num}>
                  {CATEGORY_THEMES[slug].name}
                </th>
              ))}
              <th scope="col" className={styles.num}>
                Tempo médio
              </th>
            </tr>
          </thead>
          <tbody>
            {match.scoreboard.map((line) => (
              <tr key={line.account_id} className={line.position === 1 ? styles.winnerRow : undefined}>
                <td>{line.position}º</td>
                <td>
                  {line.display_name}
                  {line.account_id === me && ' (você)'}
                  {line.left && <span className={styles.muted}> · saiu</span>}
                </td>
                <td className={styles.num}>{line.total_score}</td>
                <td className={styles.num}>{line.correct}/18</td>
                {line.per_category.map((c) => (
                  <td key={c.category} className={styles.num}>
                    {c.score} <span className={styles.muted}>({c.correct}/3)</span>
                  </td>
                ))}
                <td className={styles.num}>
                  {line.average_response_ms === null ? '—' : seconds(line.average_response_ms)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {match.history.length > 0 && (
        <details>
          <summary>As {match.history.length} músicas da partida</summary>
          <ol className={styles.list} style={{ marginTop: 10 }}>
            {match.history.map((r) => (
              <li key={r.number} className={styles.row}>
                <span className={styles.pill}>{r.number}</span>
                <span className={styles.rowGrow}>
                  <strong>{r.answer.title}</strong> — {r.answer.artist}{' '}
                  <span className={styles.muted}>· {r.category.name}</span>
                </span>
                <span className={`${styles.pill} ${r.my_status === 'won' ? styles.pillOk : styles.pillBad}`}>
                  {r.my_status === 'won' ? `+${r.my_score}` : '0'}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}

// ------------------------------------------------------------ sala de espera

function WaitingRoom({ room, actions }: { room: RoomState; actions: UseRoom }) {
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)
  const me = room.members.find((m) => m.account_id === room.me)
  const isHost = room.host_account_id === room.me
  const lastMatch = room.match && room.match.status !== 'playing' ? room.match : null

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      /* o código continua visível para ser passado à mão */
    }
  }

  return (
    <>
      {lastMatch && <FinalResults match={lastMatch} me={room.me} />}
      <div className={styles.twoCols} style={{ marginTop: lastMatch ? 20 : 0 }}>
        <section className={styles.panel} aria-labelledby="sala-jogadores">
          <div className={styles.actions}>
            <h2 id="sala-jogadores" className={styles.panelTitle}>
              Sala <span className={styles.code} data-testid="room-code">{room.code}</span>
            </h2>
            <button type="button" className="btn btn-ghost" onClick={() => void copyInvite()}>
              {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
              {copied ? 'Link copiado!' : 'Copiar convite'}
            </button>
          </div>
          <p className={styles.muted}>
            {room.members.filter((m) => !m.left).length}/{room.max_players} jogadores · mínimo de {room.min_players}
          </p>
          <ul className={styles.list} aria-label="Jogadores na sala">
            {room.members.map((m) => (
              <li key={m.account_id} className={styles.row}>
                <span
                  className={`${styles.dot} ${m.connected ? styles.dotOn : ''}`}
                  aria-label={m.connected ? 'conectado' : 'desconectado'}
                />
                <span className={styles.rowGrow}>
                  {m.display_name}
                  {m.account_id === room.me && ' (você)'}
                </span>
                {m.is_host && <Crown size={16} aria-label="anfitrião" color="var(--amber)" />}
                <span className={`${styles.pill} ${m.ready ? styles.pillOk : ''}`}>
                  {m.ready ? 'Pronto' : 'Aguardando'}
                </span>
              </li>
            ))}
          </ul>
          <div className={styles.actions}>
            {isHost ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void actions.start()}
                disabled={!room.can_start || actions.submitting}
              >
                <Play size={18} aria-hidden fill="currentColor" /> {lastMatch ? 'Nova partida' : 'Iniciar partida'}
              </button>
            ) : (
              <button
                type="button"
                className={me?.ready ? 'btn btn-secondary' : 'btn btn-primary'}
                onClick={() => void actions.setReady(!me?.ready)}
                disabled={actions.submitting}
              >
                {me?.ready ? <X size={18} aria-hidden /> : <Check size={18} aria-hidden />}
                {me?.ready ? 'Não estou pronto' : 'Estou pronto'}
              </button>
            )}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => void actions.leave().then(() => navigate('/multiplayer'))}
            >
              <DoorOpen size={18} aria-hidden /> Sair da sala
            </button>
          </div>
          {room.start_blocker && isHost && <p className={styles.muted}>{room.start_blocker}</p>}
          {actions.feedback?.kind === 'error' && (
            <p className={styles.error} role="alert">
              {actions.feedback.text}
            </p>
          )}
        </section>
        <section className={styles.panel} aria-labelledby="sala-ordem">
          <h2 id="sala-ordem" className={styles.panelTitle}>
            Ordem das categorias
          </h2>
          <p className={styles.muted}>
            {isHost ? 'Você é o anfitrião: ajuste a ordem antes de começar.' : 'Definida pelo anfitrião.'}{' '}
            Cada rodada dura até {room.round_seconds}s; acertar rápido vale até +{room.speed_bonus_max} pontos.
          </p>
          <CategoryOrder order={room.category_order} editable={isHost} onChange={(o) => void actions.setOrder(o)} />
        </section>
      </div>
    </>
  )
}

// ---------------------------------------------------------------- partida

function MatchView({ code, room, actions }: { code: string; room: RoomState; actions: UseRoom }) {
  const match = room.match as MatchState
  const online = useOnlineStatus()
  const round = match.round
  const theme = CATEGORY_THEMES[round.category.slug]
  const game = match.my_game
  const reveal = match.phase === 'reveal'
  const roundKey = `${match.id}:${round.number}`
  const fetchClip = useCallback(
    (stage: number) => api.matchAudio(code, round.number, stage),
    [code, round.number],
  )
  const player = useAudioPlayer(roundKey, fetchClip)
  const remaining = useCountdown(match.phase_ends_at, room.server_time, () => void actions.refresh())
  const { clearFeedback } = actions
  useRoundEffects(game, actions.feedback, player)

  // Rodada nova: limpa as mensagens da anterior.
  useEffect(() => {
    clearFeedback()
  }, [round.number, clearFeedback])

  const finishedMine = !!game && game.status !== 'in_progress'
  const mood = moodForGame(game, player.status === 'playing')
  const bubble = reveal
    ? 'Resposta na tela! Próxima rodada já já…'
    : finishedMine
      ? game?.status === 'won'
        ? 'Mandou bem! Agora é torcer enquanto os outros pensam…'
        : 'Essa passou… aguenta firme que vem outra!'
      : speech(game, actions.feedback, player.status === 'playing')

  return (
    <div style={{ '--accent': theme.color } as CSSProperties}>
      <header className={challenge.header}>
        <div className={styles.actions}>
          <span className={challenge.badge}>
            <theme.icon size={18} aria-hidden /> {theme.name} · música {round.index_in_category}/
            {round.songs_per_category}
          </span>
          <ConnectionBadge connection={actions.connection} />
        </div>
        <h1 className={challenge.title} data-testid="round-title">
          Rodada {match.current_round} de {match.total_rounds}
        </h1>
        <p className={challenge.date}>
          <Timer size={16} aria-hidden />
          <span
            className={`${styles.timer} ${remaining < 10_000 && !reveal ? styles.timerLow : ''}`}
            aria-live="off"
          >
            {seconds(remaining)}
          </span>
          {reveal ? 'para a próxima rodada' : 'para acabar a rodada'}
        </p>
      </header>

      <div className={challenge.layout}>
        <div className={challenge.stage}>
          <div className={challenge.mascotRow}>
            <Mascot mood={reveal || game?.status === 'won' ? 'champion' : mood} size={150} />
            <p className={challenge.bubble} aria-live="polite">
              {bubble}
            </p>
          </div>
          {reveal && match.answer ? (
            <section className={`${styles.panel} fade-up`} aria-label="Resposta da rodada">
              <AnswerCard answer={match.answer} emoji={theme.emoji} />
              {game && (
                <p className={styles.muted}>
                  {game.status === 'won'
                    ? `Você fez ${game.score} pontos (${game.score - (game.speed_bonus ?? 0)} + ${game.speed_bonus ?? 0} de bônus de velocidade).`
                    : 'Você não pontuou nesta rodada.'}
                </p>
              )}
            </section>
          ) : (
            game && (
              <AudioPlayer
                player={player}
                stages={game.stages_seconds}
                unlocked={game.unlocked_stage}
                accent={theme.color}
                finished={finishedMine}
              />
            )
          )}
        </div>

        <div className={challenge.side}>
          {game && <Attempts guesses={game.guesses} maxAttempts={game.max_attempts} inProgress={!finishedMine} />}
          {game && !finishedMine && !reveal && (
            <div className={challenge.input}>
              <GuessInput
                disabled={!online}
                submitting={actions.submitting}
                canSkip={game.remaining_attempts > 0}
                lastAttempt={game.remaining_attempts === 1}
                onGuess={actions.guess}
                onSkip={actions.skip}
              />
            </div>
          )}
          {!game && <p className={styles.muted}>Você entra a partir da próxima rodada.</p>}

          <section className={styles.panel} aria-labelledby="placar-rodada">
            <h2 id="placar-rodada" className={styles.panelTitle}>
              <Radio size={18} aria-hidden /> Placar
            </h2>
            <ul className={styles.list}>
              {match.scoreboard.map((line) => {
                const progress = match.progress.find((p) => p.account_id === line.account_id)
                return (
                  <li key={line.account_id} className={styles.row}>
                    <span className={styles.pill}>{line.position}º</span>
                    <span className={styles.rowGrow}>
                      {line.display_name}
                      {line.account_id === room.me && ' (você)'}
                      {line.left && <span className={styles.muted}> · saiu</span>}
                    </span>
                    {progress && (
                      <span
                        className={`${styles.pill} ${progress.status === 'won' ? styles.pillOk : progress.status === 'lost' ? styles.pillBad : ''}`}
                      >
                        {progress.status === 'won'
                          ? `acertou +${progress.score}`
                          : progress.status === 'lost'
                            ? 'errou'
                            : `${progress.attempts_used}/6`}
                      </span>
                    )}
                    <strong className={styles.num}>{line.total_score}</strong>
                  </li>
                )
              })}
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}

function Room({ code }: { code: string }) {
  const actions = useRoom(code, true)
  const { room, error } = actions

  useEffect(() => {
    document.title = `Sala ${code} | Músicas Babuínas`
  }, [code])

  const content = useMemo(() => {
    if (!room) return null
    if (room.status === 'playing' && room.match) return 'match'
    return 'waiting'
  }, [room])

  if (error) {
    return (
      <div className="page">
        <ErrorState error={error} onRetry={() => window.location.reload()} />
        <p style={{ textAlign: 'center' }}>
          <Link to="/multiplayer">Voltar para o multiplayer</Link>
        </p>
      </div>
    )
  }
  if (!room) return <Loading label={`Entrando na sala ${code}…`} />
  return (
    <div className="page">
      {content === 'match' ? (
        <MatchView code={code} room={room} actions={actions} />
      ) : (
        <WaitingRoom room={room} actions={actions} />
      )}
    </div>
  )
}

export function RoomPage() {
  const { code = '' } = useParams()
  const auth = useAccount()
  const clean = code.trim().toUpperCase()
  if (auth.checking) return <Loading label="Conferindo sua conta…" />
  if (!auth.account) {
    return (
      <div className="page">
        <header className={styles.intro}>
          <h1 className={styles.title}>Convite para a sala {clean}</h1>
          <p className={styles.lead}>Entre ou crie sua conta para participar.</p>
        </header>
        <AuthPanel auth={auth} />
      </div>
    )
  }
  return <Room key={clean} code={clean} />
}
