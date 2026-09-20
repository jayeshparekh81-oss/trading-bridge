'use client'

/**
 * "Tell me when this theme is ready."
 *
 * 20 Sep 2026 — this dialog collected an email address and said "We'll email you
 * when X launches". THREE measured reasons that was false:
 *   1. We cannot deliver mail to a customer at all: AWS SES is in sandbox and the
 *      send policy covers ONE identity (the admin's). Proven the same day — the
 *      weekly-report task logged AccessDenied for 12 of 13 recipients.
 *   2. The address went nowhere useful anyway: the POST target
 *      `/api/users/notify-theme` does not exist in the backend, so the address
 *      only ever reached this browser's localStorage.
 *   3. Nothing renders this dialog today (`theme-picker.tsx`, its only caller, is
 *      imported by no page), so no customer has been told this yet.
 * The email field is gone and the copy says what actually happens.
 */

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
  const [submitting, setSubmitting] = useState(false)

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    setSubmitting(true)

    // Saved on THIS device. That is the whole mechanism — no address is collected
    // and no mail is sent, because neither of those works today.
    const notifications = JSON.parse(localStorage.getItem('td-theme-notifications') || '{}')
    notifications[themeId] = { timestamp: new Date().toISOString() }
    localStorage.setItem('td-theme-notifications', JSON.stringify(notifications))

    setSubmitting(false)
    toast.success(`Saved — ${themeName} will show up here the day it is ready.`)
    onClose()
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
          <h3 className="text-lg font-semibold">Tell me when it is ready</h3>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            <strong>{themeName}</strong> is not ready yet. We&apos;ll show it right here
            the day it is — we don&apos;t send email yet, so nothing lands in your inbox.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <button
            type="submit"
            disabled={submitting}
            className="w-full h-11 rounded-xl bg-[var(--primary)] text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save my interest'}
          </button>
        </form>
      </div>
    </div>
  )
}
