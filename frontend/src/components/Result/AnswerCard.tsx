import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import type { Answer } from '../../types/api'
import styles from './ResultPanel.module.css'

/** Capa, título, artista e links da música revelada. Usado nos três modos de jogo. */
export function AnswerCard({ answer, emoji }: { answer: Answer; emoji: string }) {
  const [coverFailed, setCoverFailed] = useState(false)
  return (
    <div className={styles.answer}>
      <div className={styles.cover} aria-hidden={!answer.cover_url || coverFailed}>
        {answer.cover_url && !coverFailed ? (
          <img
            src={answer.cover_url}
            alt={`Capa de ${answer.title}`}
            width={120}
            height={120}
            loading="lazy"
            onError={() => setCoverFailed(true)}
          />
        ) : (
          <div className={styles.vinyl}>
            <span>{emoji}</span>
          </div>
        )}
      </div>
      <div className={styles.answerText}>
        <p className={styles.songTitle}>{answer.title}</p>
        <p className={styles.artist}>{answer.artist}</p>
        {(answer.spotify_url || answer.external_url) && (
          <p className={styles.links}>
            {answer.spotify_url && (
              <a href={answer.spotify_url} target="_blank" rel="noreferrer noopener" className={styles.spotify}>
                Ouvir no Spotify <ExternalLink size={14} aria-hidden />
              </a>
            )}
            {answer.external_url && (
              <a href={answer.external_url} target="_blank" rel="noreferrer noopener" className={styles.link}>
                {answer.spotify_url ? 'Abrir no Deezer' : 'Ouvir a música completa'}{' '}
                <ExternalLink size={14} aria-hidden />
              </a>
            )}
          </p>
        )}
        {answer.attribution && <p className={styles.attribution}>{answer.attribution}</p>}
      </div>
    </div>
  )
}
