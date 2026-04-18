export interface FontPair {
  id: string
  name: string
  emoji: string
  tagline: string
  heading: string
  body: string
  mono?: string
  default?: boolean
}

export const fontPairs: FontPair[] = [
  { id: 'modern-pro', name: 'Modern Pro', emoji: '\u{1F3AF}', tagline: 'Clean, Vercel-premium', heading: 'Geist', body: 'Inter', mono: 'Geist Mono', default: true },
  { id: 'premium-tech', name: 'Premium Tech', emoji: '\u{1F680}', tagline: 'Tech startup vibe', heading: 'Space Grotesk', body: 'Inter', mono: 'Space Mono' },
  { id: 'editorial-luxury', name: 'Editorial Luxury', emoji: '\u{1F48E}', tagline: 'High-end premium', heading: 'Playfair Display', body: 'Inter' },
  { id: 'fintech-sleek', name: 'Fintech Sleek', emoji: '\u{1F4CA}', tagline: 'Data-dense clarity', heading: 'Plus Jakarta Sans', body: 'DM Sans' },
  { id: 'developer-power', name: 'Developer Power', emoji: '\u26A1', tagline: 'Terminal aesthetic', heading: 'Geist', body: 'Geist', mono: 'Geist Mono' },
  { id: 'indian-premium', name: 'Indian Premium', emoji: '\u{1F1EE}\u{1F1F3}', tagline: 'Vernacular-first', heading: 'Mukta', body: 'Mukta' },
]

export function getFontById(id: string): FontPair | undefined {
  return fontPairs.find(f => f.id === id)
}
