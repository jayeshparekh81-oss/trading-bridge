'use client'

import { Check } from 'lucide-react'
import { fontPairs } from '@/lib/fonts'
import { useCustomTheme } from '@/lib/theme-context'
import { cn } from '@/lib/utils'

const fontFamilyMap: Record<string, string> = {
  'Geist': 'var(--font-geist-sans)',
  'Geist Mono': 'var(--font-geist-mono)',
  'Inter': 'var(--font-inter)',
  'Space Grotesk': 'var(--font-space-grotesk)',
  'Space Mono': 'var(--font-space-mono)',
  'Playfair Display': 'var(--font-playfair)',
  'Plus Jakarta Sans': 'var(--font-plus-jakarta)',
  'DM Sans': 'var(--font-dm-sans)',
  'Mukta': 'var(--font-mukta)',
}

export function FontPicker() {
  const { font: currentFont, setFont } = useCustomTheme()

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {fontPairs.map((fp) => {
        const isSelected = currentFont === fp.id
        const headingFamily = fontFamilyMap[fp.heading] || 'system-ui'
        const bodyFamily = fontFamilyMap[fp.body] || 'system-ui'

        return (
          <button
            key={fp.id}
            onClick={() => setFont(fp.id)}
            className={cn(
              'relative rounded-xl border p-4 text-left transition-all duration-200',
              isSelected
                ? 'border-primary ring-2 ring-primary/20 bg-primary/5'
                : 'border-border hover:border-primary/40 hover:bg-accent/50'
            )}
          >
            {isSelected && (
              <div className="absolute top-2 right-2 h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                <Check className="h-3 w-3 text-white" />
              </div>
            )}
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{fp.emoji}</span>
              <span className="font-semibold text-sm">{fp.name}</span>
            </div>
            <div
              className="text-xl font-bold mb-1 leading-tight"
              style={{ fontFamily: headingFamily }}
            >
              Aa Bb Cc
            </div>
            <div
              className="text-xs text-muted-foreground mb-1"
              style={{ fontFamily: bodyFamily }}
            >
              123,456.78
            </div>
            <div className="text-[10px] text-muted-foreground">
              {fp.heading}{fp.heading !== fp.body ? ` + ${fp.body}` : ''}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1 italic">{fp.tagline}</p>
          </button>
        )
      })}
    </div>
  )
}
