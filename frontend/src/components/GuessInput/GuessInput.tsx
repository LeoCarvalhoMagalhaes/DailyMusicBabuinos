// Campo de resposta com autocomplete acessível (padrão combobox da WAI-ARIA).
// As sugestões vêm do catálogo inteiro, nunca filtradas pela resposta do dia.

import { LoaderCircle, Search, Send, SkipForward } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { api } from '../../services/api'
import type { SongSuggestion } from '../../types/api'
import styles from './GuessInput.module.css'

interface GuessInputProps {
  disabled: boolean
  submitting: boolean
  canSkip: boolean
  lastAttempt?: boolean
  onGuess: (text: string) => Promise<boolean>
  onSkip: () => void
  search?: (q: string, signal: AbortSignal) => Promise<SongSuggestion[]>
}

const MIN_CHARS = 2

export function GuessInput({
  disabled,
  submitting,
  canSkip,
  lastAttempt = false,
  onGuess,
  onSkip,
  search = api.search,
}: GuessInputProps) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState<SongSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [searching, setSearching] = useState(false)
  const [noResults, setNoResults] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const skipNextSearch = useRef(false)
  const listId = useId()
  const hintId = useId()

  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false
      return
    }
    const q = value.trim()
    if (q.length < MIN_CHARS) {
      setSuggestions([])
      setNoResults(false)
      setOpen(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setSearching(true)
      search(q, controller.signal)
        .then((items) => {
          setSuggestions(items)
          setNoResults(items.length === 0)
          setActive(-1)
          setOpen(true)
        })
        .catch(() => {
          /* busca é auxiliar: o palpite digitado continua valendo */
        })
        .finally(() => !controller.signal.aborted && setSearching(false))
    }, 160)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [value, search])

  const choose = (item: SongSuggestion) => {
    skipNextSearch.current = true
    setValue(item.title)
    setOpen(false)
    setSuggestions([])
    inputRef.current?.focus()
  }

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    if (disabled || submitting || !value.trim()) return
    setOpen(false)
    const ok = await onGuess(value)
    if (ok) {
      skipNextSearch.current = true
      setValue('')
      setSuggestions([])
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) {
      if (event.key === 'Escape') setOpen(false)
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (i + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      choose(suggestions[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && !disabled && (suggestions.length > 0 || noResults)

  return (
    <form className={styles.form} onSubmit={submit} role="search" aria-label="Enviar palpite">
      <div className={styles.field}>
        {showList && (
          <ul id={listId} role="listbox" className={styles.list} aria-label="Sugestões de músicas">
            {suggestions.map((item, i) => (
              <li
                key={item.id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={[styles.option, i === active ? styles.optionActive : ''].join(' ')}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(item)}
              >
                <span className={styles.optionTitle}>{item.title}</span>
                <span className={styles.optionArtist}>{item.artist}</span>
              </li>
            ))}
            {noResults && (
              <li className={styles.empty} role="option" aria-selected={false} aria-disabled>
                Nenhuma música encontrada no catálogo. Você ainda pode enviar o que digitou.
              </li>
            )}
          </ul>
        )}
        <Search size={18} className={styles.searchIcon} aria-hidden />
        <input
          ref={inputRef}
          className={styles.input}
          type="text"
          inputMode="search"
          enterKeyHint="send"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          maxLength={120}
          placeholder="Qual é a música? Digite o título…"
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => {
            suggestions.length > 0 && setOpen(true)
            // No celular, garante que o campo fique visível acima do teclado virtual.
            window.setTimeout(() => inputRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }), 250)
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          aria-describedby={hintId}
          aria-label="Título da música"
        />
        {searching && <LoaderCircle size={18} className={`${styles.spinner} spin`} aria-hidden />}
      </div>
      <p id={hintId} className={styles.hint}>
        Responda com o <strong>título</strong> da música. Acentos e maiúsculas não importam.
      </p>
      <div className={styles.actions}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onSkip}
          disabled={disabled || submitting || !canSkip}
        >
          <SkipForward size={18} aria-hidden />
          {lastAttempt ? 'Desistir' : 'Pular'}
          {!lastAttempt && <span className={styles.skipExtra}>(+ pista)</span>}
        </button>
        <button type="submit" className="btn btn-primary" disabled={disabled || submitting || !value.trim()}>
          {submitting ? <LoaderCircle size={18} className="spin" aria-hidden /> : <Send size={18} aria-hidden />}
          Confirmar
        </button>
      </div>
    </form>
  )
}
