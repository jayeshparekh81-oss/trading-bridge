'use client'

import { useState } from 'react'
import { Check, Lock } from 'lucide-react'
import { themes } from '@/lib/themes'
import { useCustomTheme } from '@/lib/theme-context'
import { NotifyMeDialog } from './notify-me-dialog'
import { cn } from '@/lib/utils'

const themePreviewColors: Record<string, string[]> = {
  'cosmic-dark': ['#0A0E1A', '#3B82F6', '#00FF88', '#FF4D6A', '#A855F7'],
  'pure-light': ['#FAFAFA', '#2563EB', '#059669', '#DC2626', '#7C3AED'],
  'midnight-blue': ['#0B1929', '#00D4FF', '#10E89D', '#FF6B81', '#7DD3FC'],
  'sunset-purple': ['#1A0B2E', '#C026D3', '#F0ABFC', '#FB7185', '#E879F9'],
  'amoled-black': ['#000000', '#00FFFF', '#00FF00', '#FF0040', '#FF00FF'],
  'desi-gold': ['#FFF8E7', '#B91C1C', '#047857', '#B91C1C', '#FBBF24'],
  'emerald-forest': ['#0F2818', '#10B981', '#34D399', '#F87171', '#FCD34D'],
  'sunrise-coral': ['#FFF5F5', '#F97316', '#059669', '#DC2626', '#FB923C'],
  'cyberpunk-neon': ['#0A0A0F', '#FF0080', '#00FFAA', '#FF0080', '#00FFFF'],
  'arctic-ice': ['#F0F9FF', '#3B82F6', '#0891B2', '#DC2626', '#94A3B8'],
}

export function ThemePicker() {
  const { theme: currentTheme, setTheme } = useCustomTheme()
  const [notifyDialog, setNotifyDialog] = useState<{ open: boolean; name: string; id: string }>({
    open: false,
    name: '',
    id: '',
  })

  const activeThemes = themes.filter(t => t.active)
  const comingSoonThemes = themes.filter(t => t.comingSoon)

  return (
    <div className="space-y-6">
      {/* Active Themes */}
      <div>
        <p className="text-sm font-medium text-muted-foreground mb-3">Active Themes</p>
        <div className="grid grid-cols-2 gap-3">
          {activeThemes.map((t) => {
            const isSelected = currentTheme === t.id
            const colors = themePreviewColors[t.id] || []
            return (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
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
                <span className="text-2xl">{t.emoji}</span>
                <h4 className="font-semibold text-sm mt-2">{t.name}</h4>
                <div className="flex gap-1 mt-2">
                  {colors.map((color, i) => (
                    <div
                      key={i}
                      className="h-3 w-3 rounded-full border border-white/10"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">{t.tagline}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Coming Soon Themes */}
      <div>
        <p className="text-sm font-medium text-muted-foreground mb-3">Coming Soon</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {comingSoonThemes.map((t) => {
            const colors = themePreviewColors[t.id] || []
            const isNotified = typeof window !== 'undefined' &&
              JSON.parse(localStorage.getItem('td-theme-notifications') || '{}')[t.id]
            return (
              <div
                key={t.id}
                className="relative rounded-xl border border-border p-3 opacity-70"
              >
                <div className="absolute top-2 right-2">
                  <Lock className="h-3 w-3 text-muted-foreground" />
                </div>
                <span className="text-xl">{t.emoji}</span>
                <h4 className="font-semibold text-xs mt-1.5">{t.name}</h4>
                <div className="flex gap-0.5 mt-1.5">
                  {colors.map((color, i) => (
                    <div
                      key={i}
                      className="h-2 w-2 rounded-full border border-white/10"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">{t.tagline}</p>
                {t.premium && (
                  <span className="inline-block mt-1 text-[9px] font-bold text-accent-gold bg-accent-gold/10 px-1.5 py-0.5 rounded-full">
                    PREMIUM
                  </span>
                )}
                <button
                  onClick={() =>
                    isNotified
                      ? null
                      : setNotifyDialog({ open: true, name: t.name, id: t.id })
                  }
                  className={cn(
                    'mt-2 w-full text-[10px] font-medium py-1.5 rounded-lg transition-colors',
                    isNotified
                      ? 'bg-profit/10 text-profit cursor-default'
                      : 'bg-primary/10 text-primary hover:bg-primary/20'
                  )}
                >
                  {isNotified ? 'Notified' : 'Notify Me'}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      <NotifyMeDialog
        open={notifyDialog.open}
        onClose={() => setNotifyDialog({ open: false, name: '', id: '' })}
        themeName={notifyDialog.name}
        themeId={notifyDialog.id}
      />
    </div>
  )
}
