'use client'

import { useState } from 'react'
import { X, Bell } from 'lucide-react'
import { toast } from 'sonner'

interface NotifyMeDialogProps {
  open: boolean
  onClose: () => void
  themeName: string
  themeId: string
}

export function NotifyMeDialog({ open, onClose, themeName, themeId }: NotifyMeDialogProps) {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return

    setSubmitting(true)

    // Save to localStorage
    const notifications = JSON.parse(localStorage.getItem('td-theme-notifications') || '{}')
    notifications[themeId] = { email, timestamp: new Date().toISOString() }
    localStorage.setItem('td-theme-notifications', JSON.stringify(notifications))

    // POST to API (fire-and-forget)
    try {
      await fetch('/api/users/notify-theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, themeId, themeName }),
      })
    } catch {
      // Silently fail - localStorage is the primary store
    }

    setSubmitting(false)
    toast.success(`We'll email you when ${themeName} launches!`)
    onClose()
    setEmail('')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-sm rounded-2xl bg-[var(--card)] border border-[var(--border)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="text-center mb-6">
          <div className="h-12 w-12 rounded-full bg-[var(--primary)]/10 flex items-center justify-center mx-auto mb-3">
            <Bell className="h-6 w-6 text-[var(--primary)]" />
          </div>
          <h3 className="text-lg font-semibold">Get Notified</h3>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            We&apos;ll email you when <strong>{themeName}</strong> is available.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full h-11 px-4 rounded-xl bg-[var(--muted)] border border-[var(--border)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40"
          />
          <button
            type="submit"
            disabled={submitting || !email}
            className="w-full h-11 rounded-xl bg-[var(--primary)] text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Notify Me'}
          </button>
        </form>
      </div>
    </div>
  )
}
