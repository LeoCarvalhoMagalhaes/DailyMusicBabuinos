// Apresentação visual de cada categoria (cores, ícone e bordões).

import { AudioWaveform, Guitar, Mic, Shuffle, Sparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { CowboyHat } from '../components/Icons/CowboyHat'
import type { CategorySlug } from '../types/api'

export interface CategoryTheme {
  slug: CategorySlug
  name: string
  tagline: string
  color: string
  glow: string
  emoji: string
  icon: LucideIcon
  // Frase de efeito usada no texto de compartilhamento.
  winSlogan: string
  loseSlogan: string
}

export const CATEGORY_THEMES: Record<CategorySlug, CategoryTheme> = {
  rock: {
    slug: 'rock',
    name: 'Rock',
    tagline: 'Riffs, distorção e solos de arrepiar.',
    color: '#f43f5e',
    glow: 'rgb(244 63 94 / 0.35)',
    emoji: '🎸',
    icon: Guitar,
    winSlogan: 'Rock não se adivinha. Se sente!',
    loseSlogan: 'Hoje o amplificador queimou… amanhã tem bis!',
  },
  pop: {
    slug: 'pop',
    name: 'Pop',
    tagline: 'Refrões que grudam na cabeça.',
    color: '#e879f9',
    glow: 'rgb(232 121 249 / 0.35)',
    emoji: '🎤',
    icon: Sparkles,
    winSlogan: 'Hit reconhecido no primeiro refrão!',
    loseSlogan: 'Esse refrão escapou… mas a turnê continua.',
  },
  rap: {
    slug: 'rap',
    name: 'Rap',
    tagline: 'Rimas, batidas e flow.',
    color: '#fbbf24',
    glow: 'rgb(251 191 36 / 0.32)',
    emoji: '🎙️',
    icon: Mic,
    winSlogan: 'Flow afiado, ouvido mais ainda.',
    loseSlogan: 'Perdi a rima hoje. Amanhã volto no beat.',
  },
  country: {
    slug: 'country',
    name: 'Country',
    tagline: 'Estrada, viola e chapéu de cowboy.',
    color: '#fb923c',
    glow: 'rgb(251 146 60 / 0.32)',
    emoji: '🤠',
    icon: CowboyHat as LucideIcon,
    winSlogan: 'Laçado na primeira volta da arena!',
    loseSlogan: 'O boi fugiu hoje, mas amanhã eu laço.',
  },
  eletronica: {
    slug: 'eletronica',
    name: 'Eletrônica',
    tagline: 'Do house ao drum and bass.',
    color: '#22d3ee',
    glow: 'rgb(34 211 238 / 0.3)',
    emoji: '🎧',
    icon: AudioWaveform,
    winSlogan: 'Reconheci antes do drop!',
    loseSlogan: 'O drop me pegou de surpresa.',
  },
  geral: {
    slug: 'geral',
    name: 'Geral',
    tagline: 'Um pouco de tudo, para ouvidos ecléticos.',
    color: '#a78bfa',
    glow: 'rgb(167 139 250 / 0.35)',
    emoji: '🎶',
    icon: Shuffle,
    winSlogan: 'Ouvido eclético é outro nível!',
    loseSlogan: 'Nem todo dia é dia de show. Amanhã tem mais!',
  },
}

export const CATEGORY_ORDER: CategorySlug[] = ['rock', 'pop', 'rap', 'country', 'eletronica', 'geral']

export function isCategorySlug(value: string | undefined): value is CategorySlug {
  return !!value && (CATEGORY_ORDER as string[]).includes(value)
}
