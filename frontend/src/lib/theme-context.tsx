'use client'

import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useTheme as useNextTheme } from 'next-themes'
import { getThemeById } from './themes'
import type { ReactNode } from 'react'

interface ThemeContextType {
  theme: string
  setTheme: (theme: string) => void
  font: string
  setFont: (font: string) => void
  mode: 'auto' | 'dark' | 'light'
  setMode: (mode: 'auto' | 'dark' | 'light') => void
}

const ThemeContext = createContext<ThemeContextType | null>(null)

export function CustomThemeProvider({ children }: { children: ReactNode }) {
  const { setTheme: setNextTheme } = useNextTheme()
  const [theme, setThemeState] = useState('cosmic-dark')
  const [font, setFontState] = useState('modern-pro')
  const [mode, setModeState] = useState<'auto' | 'dark' | 'light'>('auto')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const savedTheme = localStorage.getItem('td-theme') || 'cosmic-dark'
    const savedFont = localStorage.getItem('td-font') || 'modern-pro'
    const savedMode = (localStorage.getItem('td-mode') || 'auto') as 'auto' | 'dark' | 'light'

    setThemeState(savedTheme)
    setFontState(savedFont)
    setModeState(savedMode)

    document.documentElement.setAttribute('data-theme', savedTheme)
    document.documentElement.setAttribute('data-font', savedFont)

    // Sync next-themes dark class
    const themeData = getThemeById(savedTheme)
    if (themeData) {
      setNextTheme(themeData.mode)
    }
  }, [setNextTheme])

  const setTheme = useCallback((newTheme: string) => {
    setThemeState(newTheme)
    localStorage.setItem('td-theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)

    // Sync next-themes dark class for Tailwind dark: variants
    const themeData = getThemeById(newTheme)
    if (themeData) {
      setNextTheme(themeData.mode)
    }
  }, [setNextTheme])

  const setFont = useCallback((newFont: string) => {
    setFontState(newFont)
    localStorage.setItem('td-font', newFont)
    document.documentElement.setAttribute('data-font', newFont)
  }, [])

  const setMode = useCallback((newMode: 'auto' | 'dark' | 'light') => {
    setModeState(newMode)
    localStorage.setItem('td-mode', newMode)
    if (newMode === 'dark') {
      setTheme('cosmic-dark')
    } else if (newMode === 'light') {
      setTheme('pure-light')
    } else {
      // Auto: use system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(prefersDark ? 'cosmic-dark' : 'pure-light')
    }
  }, [setTheme])

  // Listen for system theme changes in auto mode
  useEffect(() => {
    if (mode !== 'auto') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      const newTheme = e.matches ? 'cosmic-dark' : 'pure-light'
      setThemeState(newTheme)
      localStorage.setItem('td-theme', newTheme)
      document.documentElement.setAttribute('data-theme', newTheme)
      setNextTheme(e.matches ? 'dark' : 'light')
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [mode, setNextTheme])

  if (!mounted) {
    return <>{children}</>
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, font, setFont, mode, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useCustomTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useCustomTheme must be used within CustomThemeProvider')
  return ctx
}
