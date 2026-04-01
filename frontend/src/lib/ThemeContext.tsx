/* eslint-disable react-refresh/only-export-components */
/** Theme context provider (P4-26a).
 *
 * Wraps the app to provide theme state to all components.
 * The TopNav theme toggle and Plotly charts both consume this.
 */

import { createContext, useContext, useMemo } from 'react'
import type { Theme } from '@/api/preferences'
import { useTheme } from '@/lib/useTheme'

interface ThemeContextValue {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (t: Theme) => void
  cycleTheme: () => void
  isDark: boolean
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, resolvedTheme, setTheme, cycleTheme } = useTheme()

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, cycleTheme, isDark: resolvedTheme === 'dark' }),
    [theme, resolvedTheme, setTheme, cycleTheme],
  )

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useThemeContext must be used within ThemeProvider')
  return ctx
}
