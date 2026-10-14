// Efeitos sonoros discretos (sintetizados na hora, sem arquivos).
// Só tocam depois de uma interação do jogador, então respeitam o autoplay.

let ctx: AudioContext | null = null

function context(): AudioContext | null {
  try {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return null
    ctx ??= new Ctor()
    if (ctx.state === 'suspended') void ctx.resume()
    return ctx
  } catch {
    return null
  }
}

function tone(freq: number, start: number, length: number, volume: number, type: OscillatorType) {
  const ac = context()
  if (!ac) return
  const osc = ac.createOscillator()
  const gain = ac.createGain()
  osc.type = type
  osc.frequency.value = freq
  const t0 = ac.currentTime + start
  gain.gain.setValueAtTime(0.0001, t0)
  gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + length)
  osc.connect(gain).connect(ac.destination)
  osc.start(t0)
  osc.stop(t0 + length + 0.02)
}

export function playWrong(volume: number): void {
  if (volume <= 0) return
  tone(196, 0, 0.12, 0.05 * volume, 'square')
  tone(147, 0.11, 0.18, 0.05 * volume, 'square')
  navigator.vibrate?.(60)
}

export function playCorrect(volume: number): void {
  if (volume <= 0) return
  ;[523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.08, 0.22, 0.06 * volume, 'triangle'))
}
