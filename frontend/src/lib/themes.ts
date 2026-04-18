export interface Theme {
  id: string
  name: string
  emoji: string
  tagline: string
  active: boolean
  default?: boolean
  comingSoon?: boolean
  seasonal?: 'diwali' | 'holi' | 'newyear'
  premium?: boolean
  mode: 'dark' | 'light'
}

export const themes: Theme[] = [
  { id: 'cosmic-dark', name: 'Cosmic Dark', emoji: '\u{1F30C}', tagline: 'Cyberpunk trader vibe', active: true, default: true, mode: 'dark' },
  { id: 'pure-light', name: 'Pure Light', emoji: '\u2600\uFE0F', tagline: 'CRED-level premium day', active: true, default: true, mode: 'light' },
  { id: 'midnight-blue', name: 'Midnight Blue', emoji: '\u{1F48E}', tagline: 'Bloomberg terminal', active: false, comingSoon: true, mode: 'dark' },
  { id: 'sunset-purple', name: 'Sunset Purple', emoji: '\u{1F525}', tagline: 'Royal luxury', active: false, comingSoon: true, mode: 'dark' },
  { id: 'amoled-black', name: 'AMOLED Black', emoji: '\u26AB', tagline: 'Max contrast OLED', active: false, comingSoon: true, mode: 'dark' },
  { id: 'desi-gold', name: 'Desi Gold', emoji: '\u{1F1EE}\u{1F1F3}', tagline: 'Festival Diwali feel', active: false, comingSoon: true, seasonal: 'diwali', mode: 'light' },
  { id: 'emerald-forest', name: 'Emerald Forest', emoji: '\u{1F33F}', tagline: 'Growth & stability', active: false, comingSoon: true, mode: 'dark' },
  { id: 'sunrise-coral', name: 'Sunrise Coral', emoji: '\u{1F305}', tagline: 'Fresh morning trader', active: false, comingSoon: true, mode: 'light' },
  { id: 'cyberpunk-neon', name: 'Cyberpunk Neon', emoji: '\u{1F3AE}', tagline: 'Gen Z gamer', active: false, comingSoon: true, premium: true, mode: 'dark' },
  { id: 'arctic-ice', name: 'Arctic Ice', emoji: '\u{1F9CA}', tagline: 'Minimalist precision', active: false, comingSoon: true, mode: 'light' },
]

export function getThemeById(id: string): Theme | undefined {
  return themes.find(t => t.id === id)
}

export const activeThemes = themes.filter(t => t.active)
export const comingSoonThemes = themes.filter(t => t.comingSoon)
