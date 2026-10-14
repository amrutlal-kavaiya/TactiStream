import { useCallback, useState } from 'react'

import type { ThemeName } from './brand'

export const THEME_STORAGE_KEY = 'tactistream.theme'

function readStored(): ThemeName | null {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'dark' || value === 'light' ? value : null
  } catch {
    return null
  }
}

/** Stored choice first, then `prefers-color-scheme: light`, else dark. */
function initialTheme(): ThemeName {
  const stored = readStored()
  if (stored) return stored
  const prefersLight =
    typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: light)').matches
  return prefersLight ? 'light' : 'dark'
}

export interface ThemePreference {
  themeName: ThemeName
  toggleTheme: () => void
}

export function useThemePreference(): ThemePreference {
  const [themeName, setThemeName] = useState<ThemeName>(initialTheme)

  const toggleTheme = useCallback(() => {
    setThemeName((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next)
      } catch {
        // Storage can be unavailable (private mode); the toggle still applies for this visit.
      }
      return next
    })
  }, [])

  return { themeName, toggleTheme }
}
