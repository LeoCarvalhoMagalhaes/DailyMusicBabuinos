import { LoaderCircle, Lock, Pause, Play, RotateCcw, Volume2, VolumeX } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { AudioPlayer as Player } from '../../hooks/useAudioPlayer'
import { formatSeconds } from '../../utils/format'
import styles from './AudioPlayer.module.css'

interface AudioPlayerProps {
  player: Player
  stages: number[]
  unlocked: number
  accent: string
  finished: boolean
}

export function AudioPlayer({ player, stages, unlocked, accent, finished }: AudioPlayerProps) {
  const max = stages[stages.length - 1]
  const selected = player.stage ?? unlocked
  const playing = player.status === 'playing'
  const loading = player.status === 'loading'
  const clipLength = player.duration || stages[selected - 1]
  const progress = player.stage ? Math.min(player.position, clipLength) / max : 0
  const unlockedWidth = (stages[unlocked - 1] / max) * 100

  return (
    <section
      className={styles.amp}
      style={{ '--accent': accent } as CSSProperties}
      aria-label="Reprodutor de pistas"
    >
      <div className={styles.top}>
        <button
          type="button"
          className={styles.playButton}
          onClick={() => player.toggle(unlocked)}
          aria-label={playing && player.stage === unlocked ? 'Pausar trecho' : `Tocar trecho ${unlocked}`}
          disabled={loading}
        >
          {loading ? (
            <LoaderCircle className="spin" size={30} aria-hidden />
          ) : playing && player.stage === unlocked ? (
            <Pause size={30} aria-hidden fill="currentColor" />
          ) : (
            <Play size={30} aria-hidden fill="currentColor" className={styles.playIcon} />
          )}
        </button>
        <div className={styles.info}>
          <p className={styles.label}>
            {finished ? 'Ouça de novo' : `Pista ${unlocked} de ${stages.length}`}
          </p>
          <p className={styles.sub}>
            {finished
              ? 'Todos os trechos foram liberados.'
              : `${formatSeconds(stages[unlocked - 1])} de música liberados`}
          </p>
        </div>
        <div className={[styles.eq, playing ? styles.eqOn : ''].join(' ')} aria-hidden>
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>

      <div
        className={styles.track}
        role="progressbar"
        aria-label="Andamento do trecho"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={Number((progress * max).toFixed(1))}
      >
        <div className={styles.unlocked} style={{ width: `${unlockedWidth}%` }} />
        <div className={styles.progress} style={{ width: `${progress * 100}%` }} />
        {stages.slice(0, -1).map((s) => (
          <span key={s} className={styles.marker} style={{ left: `${(s / max) * 100}%` }} />
        ))}
      </div>

      <div className={styles.stages} role="group" aria-label="Trechos">
        {stages.map((seconds, i) => {
          const stage = i + 1
          const isLocked = stage > unlocked
          const active = selected === stage && player.stage !== null
          return (
            <button
              key={seconds}
              type="button"
              className={[styles.chip, active ? styles.chipActive : '', isLocked ? styles.chipLocked : '']
                .filter(Boolean)
                .join(' ')}
              disabled={isLocked || loading}
              onClick={() => player.play(stage)}
              aria-label={isLocked ? `Trecho ${stage} bloqueado` : `Ouvir trecho ${stage} (${formatSeconds(seconds)})`}
            >
              {isLocked && <Lock size={12} aria-hidden />}
              {formatSeconds(seconds)}
            </button>
          )
        })}
      </div>

      {player.error && (
        <div className={styles.error} role="alert">
          <span>{player.error}</span>
          <button type="button" className="btn btn-secondary" onClick={() => player.play(selected)}>
            <RotateCcw size={16} aria-hidden /> Tentar de novo
          </button>
        </div>
      )}

      {player.volumeSupported && (
        <label className={styles.volume}>
          <button
            type="button"
            className={styles.mute}
            onClick={() => player.setVolume(player.volume > 0 ? 0 : 0.8)}
            aria-label={player.volume > 0 ? 'Silenciar' : 'Ativar som'}
          >
            {player.volume > 0 ? <Volume2 size={18} aria-hidden /> : <VolumeX size={18} aria-hidden />}
          </button>
          <span className="visually-hidden">Volume</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={player.volume}
            onChange={(e) => player.setVolume(Number(e.target.value))}
          />
        </label>
      )}
    </section>
  )
}
