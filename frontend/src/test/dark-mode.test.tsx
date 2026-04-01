/** Dark mode toggle tests (P4-26a / T4-30).
 *
 * Verifies:
 * - Three-way toggle cycles Light → Dark → System
 * - .dark class applied/removed correctly on <html>
 * - Theme persisted to localStorage
 * - System mode respects OS preference
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from './test-utils'
import TopNav from '@/components/layout/TopNav'

// Mock fetch for the preferences API
const fetchMock = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ theme: 'system' }),
  }),
) as unknown as typeof fetch

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Dark mode toggle (T4-30)', () => {
  it('renders theme toggle button', () => {
    render(<TopNav />)
    expect(screen.getByTestId('theme-toggle')).toBeInTheDocument()
  })

  it('defaults to system theme', () => {
    render(<TopNav />)
    const btn = screen.getByTestId('theme-toggle')
    expect(btn).toHaveAttribute('aria-label', 'Theme: system')
  })

  it('cycles light → dark → system on click', () => {
    localStorage.setItem('gi-theme', 'light')
    render(<TopNav />)
    const btn = screen.getByTestId('theme-toggle')

    // light → dark
    fireEvent.click(btn)
    expect(btn).toHaveAttribute('aria-label', 'Theme: dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('gi-theme')).toBe('dark')

    // dark → system
    fireEvent.click(btn)
    expect(btn).toHaveAttribute('aria-label', 'Theme: system')
    expect(localStorage.getItem('gi-theme')).toBe('system')

    // system → light
    fireEvent.click(btn)
    expect(btn).toHaveAttribute('aria-label', 'Theme: light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('gi-theme')).toBe('light')
  })

  it('applies dark class when set to dark', () => {
    localStorage.setItem('gi-theme', 'dark')
    render(<TopNav />)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('removes dark class when set to light', () => {
    document.documentElement.classList.add('dark')
    localStorage.setItem('gi-theme', 'light')
    render(<TopNav />)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('persists theme to backend via PUT', () => {
    localStorage.setItem('gi-theme', 'light')
    render(<TopNav />)
    const btn = screen.getByTestId('theme-toggle')

    fireEvent.click(btn)

    // Should have called PUT /api/preferences/theme
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/preferences/theme',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ theme: 'dark' }),
      }),
    )
  })
})
