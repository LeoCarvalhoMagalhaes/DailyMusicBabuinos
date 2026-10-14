// Babuíno do Rock — mascote original do Músicas Babuínas, desenhado em SVG.
// Camadas fixas (juba, rosto, jaqueta, guitarra) + peças trocadas por humor
// (sobrancelhas, olhos, boca, braço, efeitos). Assim um único desenho cobre
// todos os estados do jogo e escala bem de ícone a ilustração grande.

import { useId } from 'react'
import type { MascotMood } from '../../utils/mascot'
import { MOOD_LABELS } from '../../utils/mascot'
import styles from './Mascot.module.css'

interface MascotProps {
  mood?: MascotMood
  size?: number | string
  variant?: 'full' | 'head'
  className?: string
  decorative?: boolean
}

const FUR = '#8f8373'
const FUR_DARK = '#6b6053'
const FUR_LIGHT = '#b9ab95'
const SKIN = '#e59a93'
const SKIN_DARK = '#c9726c'
const JACKET = '#18171c'
const JACKET_HI = '#34323c'

function Brows({ mood }: { mood: MascotMood }) {
  const common = { fill: FUR_DARK, stroke: FUR_DARK, strokeWidth: 2, strokeLinejoin: 'round' as const }
  switch (mood) {
    case 'doubt':
      return (
        <g {...common}>
          <path d="M95 75 Q104 66 114 74 L113 78 Q104 72 96 79 Z" />
          <path d="M126 80 Q136 79 146 83 L145 87 Q135 84 127 85 Z" />
        </g>
      )
    case 'nervous':
      return (
        <g {...common}>
          <path d="M95 82 Q103 72 114 74 L113 78 Q104 77 97 86 Z" />
          <path d="M145 82 Q137 72 126 74 L127 78 Q136 77 143 86 Z" />
        </g>
      )
    case 'win':
    case 'champion':
      return (
        <g {...common}>
          <path d="M95 74 Q104 66 114 72 L113 76 Q104 71 96 78 Z" />
          <path d="M145 74 Q136 66 126 72 L127 76 Q136 71 144 78 Z" />
        </g>
      )
    case 'lose':
      return (
        <g {...common}>
          <path d="M96 78 Q104 82 114 78 L114 82 Q104 86 96 82 Z" />
          <path d="M144 78 Q136 82 126 78 L126 82 Q136 86 144 82 Z" />
        </g>
      )
    default:
      // Confiante: uma sobrancelha arqueada, outra relaxada.
      return (
        <g {...common}>
          <path d="M95 80 Q104 75 114 79 L113 83 Q104 80 96 84 Z" />
          <path d="M126 76 Q136 68 146 76 L145 80 Q136 74 127 80 Z" />
        </g>
      )
  }
}

function Eyes({ mood }: { mood: MascotMood }) {
  if (mood === 'listening' || mood === 'win') {
    // Olhos fechados de satisfação.
    return (
      <g fill="none" stroke="#2a1714" strokeWidth={3} strokeLinecap="round">
        <path d="M99 91 Q106 85 113 91" />
        <path d="M127 91 Q134 85 141 91" />
      </g>
    )
  }
  if (mood === 'lose') {
    return (
      <g fill="none" stroke="#2a1714" strokeWidth={2.4} strokeLinecap="round">
        <path d="M106 90 m-6 0 a6 6 0 1 0 6 -6 a4 4 0 1 0 -3 5 a2 2 0 1 0 2 -2" />
        <path d="M134 90 m-6 0 a6 6 0 1 0 6 -6 a4 4 0 1 0 -3 5 a2 2 0 1 0 2 -2" />
      </g>
    )
  }
  if (mood === 'champion') return null // óculos escuros cobrem os olhos
  const pupil = mood === 'nervous' ? 2.2 : mood === 'doubt' ? 3 : 3.6
  const lid = mood === 'idle'
  return (
    <g>
      <ellipse cx={106} cy={91} rx={7.5} ry={mood === 'nervous' ? 7.5 : 6.5} fill="#f6c453" />
      <ellipse cx={134} cy={91} rx={7.5} ry={mood === 'nervous' ? 7.5 : 6.5} fill="#f6c453" />
      <circle cx={mood === 'doubt' ? 108 : 107} cy={92} r={pupil} fill="#1b0f0d" />
      <circle cx={mood === 'doubt' ? 136 : 135} cy={92} r={pupil} fill="#1b0f0d" />
      <circle cx={108.5} cy={89.5} r={1.4} fill="#fff" />
      <circle cx={136.5} cy={89.5} r={1.4} fill="#fff" />
      {lid && (
        // Pálpebras meio baixas: o olhar "de boa" de quem já sabe a resposta.
        <g fill={SKIN_DARK}>
          <path d="M98 88 Q106 82 114 88 L114 86 Q106 79 98 86 Z" />
          <path d="M126 88 Q134 82 142 88 L142 86 Q134 79 126 86 Z" />
        </g>
      )}
    </g>
  )
}

function Mouth({ mood }: { mood: MascotMood }) {
  switch (mood) {
    case 'win':
    case 'champion':
      return (
        <g>
          <path d="M100 146 Q120 168 140 146 Q120 152 100 146 Z" fill="#3a1212" />
          <path d="M103 147 Q120 152 137 147 L136 150 Q120 155 104 150 Z" fill="#fff8ee" />
          <path d="M106 148 L109 156 L111 149 Z M134 148 L131 156 L129 149 Z" fill="#fff8ee" />
          <path d="M112 158 Q120 163 128 158 Q120 156 112 158 Z" fill="#e5546a" />
        </g>
      )
    case 'doubt':
      return (
        <path
          d="M108 152 q4 -4 8 0 t8 0 t8 0"
          fill="none"
          stroke="#3a1212"
          strokeWidth={2.6}
          strokeLinecap="round"
        />
      )
    case 'nervous':
      return (
        <g>
          <rect x={104} y={146} width={32} height={10} rx={4} fill="#fff8ee" stroke="#3a1212" strokeWidth={2} />
          <path d="M112 146 V156 M120 146 V156 M128 146 V156" stroke="#3a1212" strokeWidth={1.5} />
        </g>
      )
    case 'lose':
      return (
        <g>
          <path d="M106 150 q7 -5 14 0 t14 0" fill="none" stroke="#3a1212" strokeWidth={2.6} strokeLinecap="round" />
          <path d="M122 151 q5 10 10 0" fill="#e5546a" stroke="#3a1212" strokeWidth={1.5} />
        </g>
      )
    case 'listening':
      return <path d="M110 148 Q120 156 130 148" fill="none" stroke="#3a1212" strokeWidth={2.8} strokeLinecap="round" />
    default:
      // Sorriso de canto, confiante.
      return (
        <g>
          <path d="M106 150 Q121 154 134 145" fill="none" stroke="#3a1212" strokeWidth={2.8} strokeLinecap="round" />
          <path d="M131 147 L132 152 L134 146 Z" fill="#fff8ee" />
        </g>
      )
  }
}

function Effects({ mood }: { mood: MascotMood }) {
  switch (mood) {
    case 'listening':
      return (
        <g className={styles.notes} fill="#c4b5fd">
          <g transform="translate(186 70)">
            <ellipse cx={0} cy={14} rx={6} ry={4.5} transform="rotate(-20 0 14)" />
            <rect x={4.5} y={-6} width={2.4} height={20} />
            <path d="M6.9 -6 q10 4 6 14 q0 -8 -6 -9 z" />
          </g>
          <g transform="translate(46 58) scale(0.8)" fill="#fdba74">
            <ellipse cx={0} cy={14} rx={6} ry={4.5} transform="rotate(-20 0 14)" />
            <ellipse cx={18} cy={10} rx={6} ry={4.5} transform="rotate(-20 18 10)" />
            <path d="M4 -8 h2.4 v22 h-2.4z M22 -12 h2.4 v22 h-2.4z M4 -8 l20 -4 v5 l-20 4z" />
          </g>
        </g>
      )
    case 'doubt':
      return (
        <text x={178} y={66} className={styles.question} fill="#fb923c">
          ?
        </text>
      )
    case 'nervous':
      return (
        <g className={styles.sweat} fill="#7dd3fc">
          <path d="M156 62 q6 10 0 14 q-6 -4 0 -14 z" />
          <path d="M80 70 q4 7 0 10 q-4 -3 0 -10 z" />
        </g>
      )
    case 'win':
    case 'champion':
      return (
        <g className={styles.sparkles}>
          <path d="M40 60 l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 l10 -4 z" fill="#fde047" />
          <path d="M200 40 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 l7 -3 z" fill="#fb923c" />
          <path d="M28 150 l3 6 l6 3 l-6 3 l-3 6 l-3 -6 l-6 -3 l6 -3 z" fill="#c4b5fd" />
          <path d="M30 96 l-12 16 h8 l-5 14 l14 -19 h-8 l5 -11 z" fill="#f97316" />
        </g>
      )
    case 'lose':
      return (
        <g className={styles.dizzy} fill="#fde047">
          <path d="M84 40 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 z" />
          <path d="M156 34 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 z" />
          <path d="M120 22 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 z" />
        </g>
      )
    default:
      return null
  }
}

function Guitar({ gradientId, broken }: { gradientId: string; broken: boolean }) {
  return (
    <g transform="translate(112 198) rotate(-26) scale(0.9)">
      {/* Corpo em V */}
      <path
        d="M2 -8 L-54 -36 Q-63 -38 -66 -31 L-30 -2 L-30 2 L-66 31 Q-63 38 -54 36 L2 8 Z"
        fill={`url(#${gradientId})`}
        stroke="#7c1d1d"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      <path d="M-4 -6 L-34 -20 L-42 -12 L-24 0 L-42 12 L-34 20 L-4 6 Z" fill="#fff4e6" opacity={0.9} />
      <rect x={-28} y={-9} width={7} height={18} rx={2} fill="#232025" />
      <rect x={-16} y={-9} width={7} height={18} rx={2} fill="#232025" />
      <rect x={-42} y={-7} width={4} height={14} rx={1.5} fill="#9ca3af" />
      <circle cx={-48} cy={16} r={2.6} fill="#232025" />
      <circle cx={-53} cy={22} r={2.6} fill="#232025" />
      {/* Braço e mão */}
      <rect x={0} y={-5.5} width={108} height={11} rx={2} fill="#3b2618" />
      {[16, 30, 43, 55, 66, 76, 85, 93, 100].map((x) => (
        <rect key={x} x={x} y={-5.5} width={1.4} height={11} fill="#c9b18a" />
      ))}
      <path d="M106 -7 L134 -13 Q138 -12 137 -8 L136 8 Q136 12 132 11 L106 7 Z" fill="#7c1d1d" />
      {[112, 120, 128].map((x) => (
        <g key={x}>
          <circle cx={x} cy={-12} r={2.6} fill="#d1d5db" />
          <circle cx={x} cy={12} r={2.6} fill="#d1d5db" />
        </g>
      ))}
      {/* Cordas */}
      <g stroke="#e5e7eb" strokeWidth={0.7} opacity={0.85}>
        <line x1={-40} y1={-3} x2={108} y2={-3} />
        <line x1={-40} y1={-1} x2={108} y2={-1} />
        <line x1={-40} y1={1} x2={108} y2={1} />
        {broken ? (
          <path d="M-40 3 L20 3 Q40 10 30 22 Q22 30 34 36" fill="none" className={styles.string} />
        ) : (
          <line x1={-40} y1={3} x2={108} y2={3} />
        )}
      </g>
    </g>
  )
}

export function Mascot({
  mood = 'idle',
  size = 220,
  variant = 'full',
  className,
  decorative = false,
}: MascotProps) {
  const uid = useId().replace(/:/g, '')
  const guitarGrad = `mb-guitar-${uid}`
  const furGrad = `mb-fur-${uid}`
  const viewBox = variant === 'head' ? '44 6 152 168' : '0 0 240 260'
  const raisedArm = mood === 'win' || mood === 'champion'
  const label = MOOD_LABELS[mood]

  return (
    <svg
      viewBox={viewBox}
      width={size}
      height={typeof size === 'number' && variant === 'full' ? (size * 260) / 240 : size}
      className={[styles.mascot, styles[mood], className].filter(Boolean).join(' ')}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative || undefined}
      data-mood={mood}
    >
      <defs>
        <linearGradient id={guitarGrad} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fb923c" />
          <stop offset="0.55" stopColor="#ef4444" />
          <stop offset="1" stopColor="#9f1239" />
        </linearGradient>
        <radialGradient id={furGrad} cx="0.5" cy="0.4" r="0.6">
          <stop offset="0" stopColor={FUR_LIGHT} />
          <stop offset="1" stopColor={FUR} />
        </radialGradient>
      </defs>

      {variant === 'full' && (
        <g className={styles.body}>
          {/* Jaqueta de couro */}
          <path d="M44 262 L48 204 Q54 166 92 156 L148 156 Q186 166 192 204 L196 262 Z" fill={JACKET} />
          <path d="M100 156 L140 156 L130 214 L110 214 Z" fill="#dc2626" />
          <path d="M114 170 L124 170 L118 182 L126 182 L112 200 L116 186 L109 186 Z" fill="#fde047" />
          <path d="M98 156 L84 162 L104 222 L112 212 Z" fill={JACKET_HI} />
          <path d="M142 156 L156 162 L136 222 L128 212 Z" fill={JACKET_HI} />
          <g fill="#d1d5db">
            {[60, 70, 80].map((x, i) => (
              <circle key={`l${x}`} cx={x} cy={178 - i * 6} r={2.4} />
            ))}
            {[160, 170, 180].map((x, i) => (
              <circle key={`r${x}`} cx={x} cy={166 + i * 6} r={2.4} />
            ))}
          </g>
          <circle cx={150} cy={196} r={7} fill="#8b5cf6" stroke="#ede9fe" strokeWidth={1.5} />
          <path d="M148 192 v7 a2 2 0 1 1 -1.5 -1.9 V192 h5 v2 h-3.5" fill="#ede9fe" />
          {/* Alça da guitarra */}
          <path d="M150 158 L70 226" stroke="#7c2d12" strokeWidth={7} strokeLinecap="round" />
        </g>
      )}

      {variant === 'full' && (
        <g className={styles.arms}>
          <path d="M64 186 Q62 220 96 214" fill="none" stroke={JACKET} strokeWidth={24} strokeLinecap="round" />
          <path d="M64 186 Q62 220 96 214" fill="none" stroke={JACKET_HI} strokeWidth={3} strokeLinecap="round" opacity={0.6} />
          {raisedArm ? (
            <path d="M180 186 Q218 172 222 120" fill="none" stroke={JACKET} strokeWidth={22} strokeLinecap="round" />
          ) : (
            <path d="M178 186 Q206 206 174 172" fill="none" stroke={JACKET} strokeWidth={22} strokeLinecap="round" />
          )}
        </g>
      )}

      {variant === 'full' && <Guitar gradientId={guitarGrad} broken={mood === 'lose'} />}

      {variant === 'full' && (
        <g>
          <g className={styles.strum}>
            <ellipse cx={100} cy={212} rx={11} ry={10} fill={FUR} stroke={FUR_DARK} strokeWidth={1.5} />
            <path d="M95 205 q6 -3 10 2 M94 210 q7 -2 11 3" stroke={FUR_DARK} strokeWidth={2} fill="none" />
            <path d="M106 210 l10 -6 l2 4 l-9 5 z" fill="#fde047" />
          </g>
          {!raisedArm && (
            <g>
              <ellipse cx={168} cy={168} rx={10} ry={10} fill={FUR} stroke={FUR_DARK} strokeWidth={1.5} />
              <path d="M161 163 q6 -2 10 3 M160 168 q6 -2 10 3" stroke={FUR_DARK} strokeWidth={1.8} fill="none" />
            </g>
          )}
        </g>
      )}

      <g className={styles.head}>
        {/* Juba espetada: a silhueta do personagem */}
        <path
          d="M64 132 L36 116 Q50 108 54 98 L30 78 Q48 74 56 70 L42 46 Q62 48 72 54 L68 22
             Q86 34 92 42 L102 6 Q112 26 116 36 L134 4 Q138 26 140 36 L164 12 Q160 34 160 44
             L192 32 Q182 52 180 60 L208 64 Q194 78 188 84 L210 104 Q192 108 184 112 L198 132
             Q184 136 178 138 Q170 154 150 158 L90 158 Q70 154 64 132 Z"
          fill={`url(#${furGrad})`}
          stroke={FUR_DARK}
          strokeWidth={2}
          strokeLinejoin="round"
        />
        <g fill="none" stroke={FUR_DARK} strokeWidth={2} strokeLinecap="round" opacity={0.7}>
          <path d="M72 58 q12 2 16 14" />
          <path d="M160 48 q-10 4 -14 16" />
          <path d="M52 100 q10 2 14 12" />
          <path d="M188 100 q-10 2 -14 12" />
          <path d="M116 40 q2 10 -2 18" />
          <path d="M92 46 q4 8 2 16" />
          <path d="M140 40 q-2 10 2 18" />
        </g>
        {/* Orelhas */}
        <ellipse cx={74} cy={98} rx={8} ry={11} fill={SKIN_DARK} />
        <ellipse cx={166} cy={98} rx={8} ry={11} fill={SKIN_DARK} />
        {/* Bochechas claras */}
        <ellipse cx={92} cy={116} rx={20} ry={26} fill={FUR_LIGHT} />
        <ellipse cx={148} cy={116} rx={20} ry={26} fill={FUR_LIGHT} />
        {/* Máscara facial e focinho alongado de babuíno */}
        <path
          d="M90 82 Q120 66 150 82 Q158 96 148 106 L144 136 Q141 156 120 156 Q99 156 96 136 L92 106 Q82 96 90 82 Z"
          fill={SKIN}
          stroke={SKIN_DARK}
          strokeWidth={2}
        />
        <path d="M114 100 Q120 96 126 100 L124 128 Q120 131 116 128 Z" fill="#f2b5ae" opacity={0.8} />
        <path d="M110 108 Q112 122 110 132 M130 108 Q128 122 130 132" stroke={SKIN_DARK} strokeWidth={1.6} fill="none" opacity={0.7} />
        <ellipse cx={113} cy={138} rx={4} ry={3} fill="#5b2626" />
        <ellipse cx={127} cy={138} rx={4} ry={3} fill="#5b2626" />
        <Eyes mood={mood} />
        <Brows mood={mood} />
        <Mouth mood={mood} />
        {/* Óculos escuros: na cabeça, ou nos olhos na pose de campeão */}
        <g transform={mood === 'champion' ? 'translate(0 0)' : 'translate(0 -36)'}>
          <path d="M94 84 h24 q2 12 -6 14 h-12 q-8 -2 -6 -14 z" fill="#111" stroke="#f97316" strokeWidth={1.5} />
          <path d="M122 84 h24 q2 12 -6 14 h-12 q-8 -2 -6 -14 z" fill="#111" stroke="#f97316" strokeWidth={1.5} />
          <path d="M118 87 h4" stroke="#f97316" strokeWidth={2} />
          <path d="M98 87 l6 0" stroke="#fff" strokeWidth={1.5} opacity={0.5} />
          <path d="M126 87 l6 0" stroke="#fff" strokeWidth={1.5} opacity={0.5} />
        </g>
      </g>

      {variant === 'full' && raisedArm && (
        // Mão fazendo o sinal do rock, na frente da juba.
        <g className={styles.horns}>
          <rect x={208} y={80} width={6.5} height={28} rx={3.2} fill={FUR} stroke={FUR_DARK}
            strokeWidth={1.2} transform="rotate(-14 211 106)" />
          <rect x={229} y={84} width={6} height={24} rx={3} fill={FUR} stroke={FUR_DARK}
            strokeWidth={1.2} transform="rotate(16 232 106)" />
          <ellipse cx={221} cy={113} rx={13} ry={11} fill={FUR} stroke={FUR_DARK} strokeWidth={1.5} />
          <path d="M214 106 q4 -4 7 0 q4 -4 7 0" stroke={FUR_DARK} strokeWidth={1.8} fill="none" />
          <path d="M210 114 q8 -4 14 2" stroke={FUR_DARK} strokeWidth={2} fill="none" />
        </g>
      )}
      <Effects mood={mood} />
    </svg>
  )
}
