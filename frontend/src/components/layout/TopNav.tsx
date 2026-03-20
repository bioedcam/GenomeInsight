import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Dna, Sun, Moon, Monitor, Search } from 'lucide-react'
import SampleSwitcher from './SampleSwitcher'
import CommandPalette from '@/components/CommandPalette'

type Theme = 'light' | 'dark' | 'system'

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

export default function TopNav() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem('gi-theme')
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
  })
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem('gi-theme', theme)

    if (theme === 'system') {
      const mql = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = () => applyTheme('system')
      mql.addEventListener('change', handler)
      return () => mql.removeEventListener('change', handler)
    }
  }, [theme])

  // Global Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setPaletteOpen((prev) => !prev)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const cycleTheme = () => {
    const order: Theme[] = ['light', 'dark', 'system']
    setTheme(order[(order.indexOf(theme) + 1) % 3])
  }

  const openPalette = useCallback(() => setPaletteOpen(true), [])

  const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor

  return (
    <header className="h-12 border-b border-border bg-background flex items-center px-4 gap-4 shrink-0">
      <Link to="/" className="flex items-center gap-2 font-semibold text-foreground">
        <Dna className="h-5 w-5 text-primary" />
        <span>GenomeInsight</span>
      </Link>

      <div className="flex-1" />

      {/* Sample switcher (P1-16) */}
      <SampleSwitcher />

      {/* Command palette trigger (P2-18) */}
      <button
        type="button"
        onClick={openPalette}
        className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground border border-input rounded-md px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition-colors"
        aria-label="Open command palette"
        data-testid="command-palette-trigger"
      >
        <Search className="h-3.5 w-3.5" />
        <span>Search...</span>
        <kbd className="ml-2 text-xs bg-muted text-secondary-foreground px-1.5 py-0.5 rounded">{/Mac|iPhone|iPad/.test(navigator.userAgent) ? '⌘' : 'Ctrl+'}K</kbd>
      </button>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* Dark mode toggle */}
      <button
        type="button"
        onClick={cycleTheme}
        className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-accent-foreground transition-colors"
        aria-label={`Theme: ${theme}`}
        title={`Theme: ${theme}`}
      >
        <ThemeIcon className="h-4 w-4" />
      </button>
    </header>
  )
}
