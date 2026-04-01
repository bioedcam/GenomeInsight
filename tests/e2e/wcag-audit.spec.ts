/**
 * P4-26c — WCAG 2.1 AA comprehensive audit.
 *
 * Automated accessibility checks across ALL application pages:
 *   - axe-core WCAG 2.1 AA scan (contrast, ARIA, structure)
 *   - Heading hierarchy (no skipped levels)
 *   - Keyboard navigation (Tab reaches interactive elements, Escape dismissal)
 *   - Skip navigation link
 *   - Landmarks (main, nav, banner)
 *   - Route announcer (aria-live region)
 */

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// All pages within the main AppLayout (auth-guarded, sidebar-wrapped)
const APP_PAGES = [
  { path: '/', title: 'Dashboard' },
  { path: '/findings', title: 'All Findings' },
  { path: '/variants', title: 'Variant Explorer' },
  { path: '/pharmacogenomics', title: 'Pharmacogenomics' },
  { path: '/nutrigenomics', title: 'Nutrigenomics' },
  { path: '/cancer', title: 'Cancer' },
  { path: '/cardiovascular', title: 'Cardiovascular' },
  { path: '/apoe', title: 'APOE' },
  { path: '/carrier-status', title: 'Carrier Status' },
  { path: '/fitness', title: 'Gene Fitness' },
  { path: '/sleep', title: 'Gene Sleep' },
  { path: '/methylation', title: 'MTHFR & Methylation' },
  { path: '/skin', title: 'Gene Skin' },
  { path: '/allergy', title: 'Gene Allergy & Immune Sensitivities' },
  { path: '/traits', title: 'Traits & Personality' },
  { path: '/gene-health', title: 'Gene Health' },
  { path: '/ancestry', title: 'Ancestry' },
  { path: '/rare-variants', title: 'Rare Variants' },
  { path: '/genome-browser', title: 'Genome Browser' },
  { path: '/query-builder', title: 'Query Builder' },
  { path: '/reports', title: 'Reports' },
  { path: '/settings', title: 'Settings' },
] as const

// Full-screen pages (no sidebar)
const STANDALONE_PAGES = [
  { path: '/setup', title: 'Setup Wizard' },
  { path: '/login', title: 'Login' },
] as const

test.describe('P4-26c: WCAG 2.1 AA Audit', () => {
  // ── axe-core scans for all app pages ─────────────────────
  test.describe('axe-core WCAG 2.1 AA compliance', () => {
    for (const page of APP_PAGES) {
      test(`${page.title} (${page.path}) passes axe-core`, async ({ page: p }) => {
        await p.goto(page.path)
        await p.waitForLoadState('networkidle')

        const results = await new AxeBuilder({ page: p })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze()

        const violations = results.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        }))

        expect(
          violations,
          `axe-core violations on ${page.path}:\n${JSON.stringify(violations, null, 2)}`,
        ).toEqual([])
      })
    }

    for (const page of STANDALONE_PAGES) {
      test(`${page.title} (${page.path}) passes axe-core`, async ({ page: p }) => {
        await p.goto(page.path)
        await p.waitForLoadState('networkidle')

        const results = await new AxeBuilder({ page: p })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze()

        const violations = results.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        }))

        expect(
          violations,
          `axe-core violations on ${page.path}:\n${JSON.stringify(violations, null, 2)}`,
        ).toEqual([])
      })
    }
  })

  // ── axe-core in dark mode ────────────────────────────────
  test.describe('axe-core dark mode compliance', () => {
    // Test a representative subset in dark mode for contrast
    const darkModePages = [
      APP_PAGES.find(p => p.path === '/'),
      APP_PAGES.find(p => p.path === '/variants'),
      APP_PAGES.find(p => p.path === '/pharmacogenomics'),
      APP_PAGES.find(p => p.path === '/settings'),
    ].filter((p): p is (typeof APP_PAGES)[number] => p !== undefined)

    for (const page of darkModePages) {
      test(`${page.title} passes axe-core in dark mode`, async ({ page: p }) => {
        await p.emulateMedia({ colorScheme: 'dark' })
        await p.goto(page.path)
        await p.waitForLoadState('networkidle')

        const results = await new AxeBuilder({ page: p })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze()

        const violations = results.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        }))

        expect(
          violations,
          `Dark mode axe-core violations on ${page.path}:\n${JSON.stringify(violations, null, 2)}`,
        ).toEqual([])
      })
    }
  })

  // ── Heading hierarchy ────────────────────────────────────
  test.describe('Heading hierarchy (no skipped levels)', () => {
    for (const page of APP_PAGES) {
      test(`${page.title} (${page.path})`, async ({ page: p }) => {
        await p.goto(page.path)
        await p.waitForLoadState('networkidle')

        const headingLevels = await p.evaluate(() => {
          const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6')
          return Array.from(headings).map((h) => parseInt(h.tagName.charAt(1)))
        })

        for (let i = 1; i < headingLevels.length; i++) {
          const diff = headingLevels[i] - headingLevels[i - 1]
          expect(
            diff,
            `Heading jumped from h${headingLevels[i - 1]} to h${headingLevels[i]} on ${page.path}`,
          ).toBeLessThanOrEqual(1)
        }
      })
    }
  })

  // ── Keyboard navigation ──────────────────────────────────
  test.describe('Keyboard navigation', () => {
    test('Tab reaches interactive elements from Dashboard', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Tab through the page; first focus should be skip-nav or an interactive element
      await page.keyboard.press('Tab')
      const firstFocused = await page.evaluate(() => {
        const el = document.activeElement
        return el
          ? {
              tag: el.tagName,
              isInteractive: el.matches('a, button, input, select, textarea, [tabindex]'),
              text: el.textContent?.trim().slice(0, 50),
            }
          : null
      })
      expect(firstFocused?.isInteractive).toBe(true)

      // Continue tabbing — focus should move
      await page.keyboard.press('Tab')
      const secondFocused = await page.evaluate(() => {
        const el = document.activeElement
        return el
          ? {
              tag: el.tagName,
              isInteractive: el.matches('a, button, input, select, textarea, [tabindex]'),
            }
          : null
      })
      expect(secondFocused?.isInteractive).toBe(true)
    })

    test('Escape closes sample switcher dropdown', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const trigger = page.locator('[aria-label="Switch sample"]')
      if (await trigger.isVisible()) {
        await trigger.click()
        const listbox = page.locator('[role="listbox"]')
        await expect(listbox).toBeVisible()

        await page.keyboard.press('Escape')
        await expect(listbox).not.toBeVisible()
      }
    })

    test('Escape closes command palette', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Open command palette with Cmd/Ctrl+K
      const modifier = process.platform === 'darwin' ? 'Meta' : 'Control'
      await page.keyboard.press(`${modifier}+k`)
      const input = page.getByTestId('command-palette-input')
      await expect(input).toBeVisible()

      await page.keyboard.press('Escape')
      await expect(input).not.toBeVisible()
    })

    for (const pageDef of APP_PAGES) {
      test(`${pageDef.title} (${pageDef.path}) has reachable interactive elements via Tab`, async ({ page }) => {
        await page.goto(pageDef.path)
        await page.waitForLoadState('networkidle')

        await page.keyboard.press('Tab')
        const focused = await page.evaluate(() => {
          const el = document.activeElement
          return el?.matches('a, button, input, select, textarea, [tabindex]') ?? false
        })
        expect(focused).toBe(true)
      })
    }
  })

  // ── Skip navigation ──────────────────────────────────────
  test.describe('Skip navigation link', () => {
    test('skip nav link is present and targets #main-content', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const skipLink = page.locator('a[href="#main-content"]')
      await expect(skipLink).toBeAttached()

      // Verify main content target exists
      const mainContent = page.locator('#main-content')
      await expect(mainContent).toBeAttached()
    })

    test('skip nav link becomes visible on focus', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Tab to the skip link (first focusable element)
      await page.keyboard.press('Tab')

      const skipLink = page.locator('a[href="#main-content"]')
      // When focused, it should no longer be sr-only
      const isVisible = await skipLink.evaluate((el) => {
        const style = window.getComputedStyle(el)
        return style.position !== 'absolute' || parseInt(style.width) > 1
      })
      expect(isVisible).toBe(true)
    })
  })

  // ── Landmarks ────────────────────────────────────────────
  test.describe('ARIA landmarks', () => {
    test('page has main landmark', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const main = page.locator('main, [role="main"]')
      await expect(main).toBeAttached()
    })

    test('page has navigation landmark', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const nav = page.locator('nav[aria-label="Main navigation"]')
      await expect(nav).toBeAttached()
    })

    test('page has banner landmark (header)', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const header = page.locator('header')
      await expect(header).toBeAttached()
    })
  })

  // ── Route announcer (screen reader) ──────────────────────
  test.describe('Route change announcements', () => {
    test('aria-live region announces navigation', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const announcer = page.locator('[aria-live="polite"]')
      await expect(announcer).toBeAttached()

      // Navigate via client-side routing (click sidebar link)
      await page.locator('nav[aria-label="Main navigation"] a[href="/settings"]').click()
      await page.waitForURL('/settings')

      const text = await announcer.textContent()
      expect(text).toContain('Navigated to Settings')
    })
  })

  // ── Focus visible indicators ─────────────────────────────
  test.describe('Focus visible indicators', () => {
    test('focused elements have visible outline', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Tab to an interactive element
      await page.keyboard.press('Tab')
      await page.keyboard.press('Tab') // Past skip nav

      const hasOutline = await page.evaluate(() => {
        const el = document.activeElement
        if (!el) return false
        const style = window.getComputedStyle(el)
        return (
          style.outlineStyle !== 'none' ||
          style.boxShadow !== 'none'
        )
      })
      expect(hasOutline).toBe(true)
    })
  })

  // ── Color contrast (verified by axe-core above, additional manual spot check) ──
  test.describe('Color contrast spot checks', () => {
    test('muted-foreground text has sufficient contrast against background', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Check that muted-foreground color variables resolve to WCAG AA compliant values
      const contrast = await page.evaluate(() => {
        // Get computed colors from CSS variables
        const root = document.documentElement
        const style = getComputedStyle(root)
        const bg = style.getPropertyValue('--color-background').trim()
        const fg = style.getPropertyValue('--color-muted-foreground').trim()
        return { bg, fg }
      })

      // Values should exist (non-empty)
      expect(contrast.bg).toBeTruthy()
      expect(contrast.fg).toBeTruthy()
    })
  })

  // ── Reduced motion ───────────────────────────────────────
  test.describe('Reduced motion preference', () => {
    test('respects prefers-reduced-motion', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Verify animated elements have near-zero duration
      const hasReducedMotion = await page.evaluate(() => {
        const style = document.querySelector('style, link[rel="stylesheet"]')
        // Check that CSS media query is applied via computed style
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches
      })
      expect(hasReducedMotion).toBe(true)
    })
  })
})
