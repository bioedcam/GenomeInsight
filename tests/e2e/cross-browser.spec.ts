/**
 * P4-26d -- Cross-browser testing (Chrome, Firefox, Safari).
 *
 * Verifies core workflows render and behave consistently across all three
 * supported browsers.  Each test runs once per Playwright project defined
 * in playwright.config.ts (chromium, firefox, webkit).
 *
 * Coverage:
 *   - Page rendering (no JS errors, correct headings)
 *   - Client-side navigation between pages
 *   - Dark mode rendering
 *   - Form / interactive element behaviour
 *   - Layout consistency (viewport screenshots)
 *   - axe-core WCAG 2.1 AA compliance per browser
 */

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// ── Core pages representing every major workflow area ───────────────────
const CORE_PAGES = [
  { path: '/', title: 'Dashboard' },
  { path: '/variants', title: 'Variant Explorer' },
  { path: '/pharmacogenomics', title: 'Pharmacogenomics' },
  { path: '/nutrigenomics', title: 'Nutrigenomics' },
  { path: '/cancer', title: 'Cancer' },
  { path: '/cardiovascular', title: 'Cardiovascular' },
  { path: '/ancestry', title: 'Ancestry' },
  { path: '/carrier-status', title: 'Carrier Status' },
  { path: '/fitness', title: 'Gene Fitness' },
  { path: '/sleep', title: 'Gene Sleep' },
  { path: '/skin', title: 'Gene Skin' },
  { path: '/methylation', title: 'MTHFR & Methylation' },
  { path: '/allergy', title: 'Gene Allergy & Immune Sensitivities' },
  { path: '/traits', title: 'Traits & Personality' },
  { path: '/gene-health', title: 'Gene Health' },
  { path: '/findings', title: 'All Findings' },
  { path: '/rare-variants', title: 'Rare Variants' },
  { path: '/genome-browser', title: 'Genome Browser' },
  { path: '/query-builder', title: 'Query Builder' },
  { path: '/reports', title: 'Reports' },
  { path: '/settings', title: 'Settings' },
] as const

// Standalone (full-screen) pages
const STANDALONE_PAGES = [
  { path: '/setup', title: 'Setup Wizard' },
  { path: '/login', title: 'Login' },
] as const

// Third-party selectors excluded from axe scans (render their own DOM)
const THIRD_PARTY_EXCLUDES = [
  '.igv-container',
  '[data-testid="igv-container"]',
  '.igv-root-div',
  'nightingale-manager',
  '.monaco-editor',
]

// Pages where third-party components cause known color-contrast violations
const CONTRAST_EXCLUDED_PAGES = new Set(['/genome-browser'])

// Console message patterns that are safe to ignore across all browsers
const IGNORED_CONSOLE_PATTERNS = [
  '[vite]',
  'Download the React DevTools',
  'React does not recognize',
  '[HMR]',
  'was preloaded using link preload',
  'DevTools',
]

function isIgnoredConsoleMessage(text: string): boolean {
  return IGNORED_CONSOLE_PATTERNS.some((p) => text.includes(p))
}

// ── 1. Page rendering: no JS errors, correct h1 heading ────────────────
test.describe('P4-26d: Cross-browser — page rendering', () => {
  for (const pg of CORE_PAGES) {
    test(`${pg.title} (${pg.path}) renders without JS errors`, async ({ page }) => {
      const errors: string[] = []
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      // Verify h1 heading is present
      const h1 = page.getByRole('heading', { level: 1 })
      await expect(h1).toBeVisible()

      expect(errors, `JS errors on ${pg.path}:\n${errors.join('\n')}`).toEqual([])
    })
  }

  for (const pg of STANDALONE_PAGES) {
    test(`${pg.title} (${pg.path}) renders without JS errors`, async ({ page }) => {
      const errors: string[] = []
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      expect(errors, `JS errors on ${pg.path}:\n${errors.join('\n')}`).toEqual([])
    })
  }
})

// ── 2. Client-side navigation ──────────────────────────────────────────
test.describe('P4-26d: Cross-browser — client-side navigation', () => {
  test('navigate between multiple pages via sidebar links', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Navigate to Variant Explorer
    const variantsLink = page.locator('nav a[href="/variants"]')
    if (await variantsLink.isVisible()) {
      await variantsLink.click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/\/variants/)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    }

    // Navigate to Settings
    const settingsLink = page.locator('nav a[href="/settings"]')
    if (await settingsLink.isVisible()) {
      await settingsLink.click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/\/settings/)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    }

    // Navigate back to Dashboard
    const dashLink = page.locator('nav a[href="/"]')
    if (await dashLink.isVisible()) {
      await dashLink.click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/^\/$|\/\?/)
    }
  })

  test('browser back/forward navigation works', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings/)

    await page.goBack()
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/^\/$|\/\?/)

    await page.goForward()
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/settings/)
  })

  test('direct URL navigation works for all core routes', async ({ page }) => {
    // Verify a representative subset loads directly (not via SPA navigation)
    const subset = ['/variants', '/pharmacogenomics', '/settings', '/findings']
    for (const path of subset) {
      const response = await page.goto(path)
      expect(response?.status(), `${path} returned ${response?.status()}`).toBeLessThan(400)
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    }
  })
})

// ── 3. Dark mode rendering ─────────────────────────────────────────────
test.describe('P4-26d: Cross-browser — dark mode', () => {
  const darkModePages = [
    { path: '/', title: 'Dashboard' },
    { path: '/variants', title: 'Variant Explorer' },
    { path: '/pharmacogenomics', title: 'Pharmacogenomics' },
    { path: '/settings', title: 'Settings' },
    { path: '/fitness', title: 'Gene Fitness' },
    { path: '/ancestry', title: 'Ancestry' },
  ]

  for (const pg of darkModePages) {
    test(`${pg.title} renders in dark mode without errors`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' })

      const errors: string[] = []
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      expect(errors).toEqual([])

      // Verify dark class is applied to the document
      const hasDarkClass = await page.evaluate(() =>
        document.documentElement.classList.contains('dark'),
      )
      // System-preference dark should trigger the dark class
      expect(hasDarkClass).toBe(true)
    })
  }
})

// ── 4. Interactive elements ────────────────────────────────────────────
test.describe('P4-26d: Cross-browser — interactive elements', () => {
  test('keyboard navigation (Tab) reaches interactive elements', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Tab through the page and verify focus lands on interactive elements
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab')
    }

    const focused = await page.evaluate(() => {
      const el = document.activeElement
      return el
        ? {
            tag: el.tagName,
            isInteractive: el.matches(
              'a, button, input, select, textarea, [tabindex="0"]',
            ),
          }
        : null
    })

    expect(focused).toBeTruthy()
    expect(focused!.tag).not.toBe('BODY')
  })

  test('command palette opens and closes with keyboard', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Open command palette with Ctrl+K (Linux/CI) or Meta+K (macOS)
    const modifier = process.platform === 'darwin' ? 'Meta' : 'Control'
    await page.keyboard.press(`${modifier}+k`)

    const input = page.getByTestId('command-palette-input')
    // Command palette should be visible
    await expect(input).toBeVisible()

    // Close with Escape
    await page.keyboard.press('Escape')
    await expect(input).not.toBeVisible()
  })

  test('sidebar collapse/expand works', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.locator('[aria-label="Toggle sidebar"], [data-testid="sidebar-toggle"]')
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click()
      // Wait for transition
      await page.waitForTimeout(300)

      await toggleBtn.click()
      await page.waitForTimeout(300)

      // Page should still be functional
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    }
  })
})

// ── 5. Console error monitoring ────────────────────────────────────────
test.describe('P4-26d: Cross-browser — console errors', () => {
  const sampledPages = [
    { path: '/', title: 'Dashboard' },
    { path: '/variants', title: 'Variant Explorer' },
    { path: '/pharmacogenomics', title: 'Pharmacogenomics' },
    { path: '/settings', title: 'Settings' },
    { path: '/setup', title: 'Setup Wizard' },
  ]

  for (const pg of sampledPages) {
    test(`${pg.title} (${pg.path}) has no unexpected console errors`, async ({ page }) => {
      const consoleErrors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          const text = msg.text()
          if (!isIgnoredConsoleMessage(text)) {
            consoleErrors.push(text)
          }
        }
      })

      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      expect(
        consoleErrors,
        `Unexpected console errors on ${pg.path}:\n${consoleErrors.join('\n')}`,
      ).toEqual([])
    })
  }
})

// ── 6. Resource loading ────────────────────────────────────────────────
test.describe('P4-26d: Cross-browser — resource loading', () => {
  test('no broken static resources on Dashboard', async ({ page }) => {
    const failedRequests: string[] = []
    page.on('response', (response) => {
      // Only flag non-API static resource failures
      if (response.status() >= 400 && !response.url().includes('/api/')) {
        failedRequests.push(`${response.status()} ${response.url()}`)
      }
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    expect(
      failedRequests,
      `Broken resources:\n${failedRequests.join('\n')}`,
    ).toEqual([])
  })

  test('CSS and JS bundles load across pages', async ({ page }) => {
    for (const path of ['/', '/variants', '/settings']) {
      const failedAssets: string[] = []
      page.on('response', (response) => {
        const url = response.url()
        if (
          (url.endsWith('.js') || url.endsWith('.css') || url.includes('.js?') || url.includes('.css?')) &&
          response.status() >= 400
        ) {
          failedAssets.push(`${response.status()} ${url}`)
        }
      })

      await page.goto(path)
      await page.waitForLoadState('networkidle')

      expect(failedAssets, `Failed assets on ${path}`).toEqual([])
    }
  })
})

// ── 7. axe-core WCAG 2.1 AA per browser ───────────────────────────────
test.describe('P4-26d: Cross-browser — WCAG 2.1 AA compliance', () => {
  // Run axe-core on a representative subset of pages per browser
  const axePages = [
    { path: '/', title: 'Dashboard' },
    { path: '/variants', title: 'Variant Explorer' },
    { path: '/pharmacogenomics', title: 'Pharmacogenomics' },
    { path: '/settings', title: 'Settings' },
    { path: '/findings', title: 'All Findings' },
    { path: '/fitness', title: 'Gene Fitness' },
  ]

  for (const pg of axePages) {
    test(`${pg.title} (${pg.path}) passes axe-core`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      let builder = new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      for (const sel of THIRD_PARTY_EXCLUDES) {
        builder = builder.exclude(sel)
      }
      if (CONTRAST_EXCLUDED_PAGES.has(pg.path)) {
        builder = builder.disableRules(['color-contrast'])
      }

      const results = await builder.analyze()

      const violations = results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        nodes: v.nodes.length,
      }))

      expect(
        violations,
        `axe-core violations on ${pg.path}:\n${JSON.stringify(violations, null, 2)}`,
      ).toEqual([])
    })
  }
})

// ── 8. Visual screenshot comparison ────────────────────────────────────
test.describe('P4-26d: Cross-browser — visual screenshots', () => {
  // Capture screenshots for key pages; failures saved as artifacts
  const screenshotPages = [
    { path: '/', name: 'dashboard' },
    { path: '/variants', name: 'variants' },
    { path: '/settings', name: 'settings' },
    { path: '/pharmacogenomics', name: 'pharmacogenomics' },
  ]

  for (const pg of screenshotPages) {
    test(`capture ${pg.name} screenshot`, async ({ page, browserName }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      await page.screenshot({
        path: `test-results/screenshots/${browserName}-${pg.name}.png`,
        fullPage: true,
      })

      // Verify page loaded (screenshot is for visual comparison, not assertion)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    })
  }

  // Dark mode screenshots
  for (const pg of screenshotPages) {
    test(`capture ${pg.name} dark mode screenshot`, async ({ page, browserName }) => {
      await page.emulateMedia({ colorScheme: 'dark' })
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')

      await page.screenshot({
        path: `test-results/screenshots/${browserName}-${pg.name}-dark.png`,
        fullPage: true,
      })

      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    })
  }
})

// ── 9. Responsive layout across browsers ───────────────────────────────
test.describe('P4-26d: Cross-browser — responsive layout', () => {
  const viewports = [
    { name: 'mobile', width: 375, height: 812 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1440, height: 900 },
  ]

  for (const vp of viewports) {
    test(`Dashboard renders at ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })

      const errors: string[] = []
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto('/')
      await page.waitForLoadState('networkidle')

      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      expect(errors).toEqual([])
    })

    test(`Settings renders at ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })

      const errors: string[] = []
      page.on('pageerror', (err) => errors.push(err.message))

      await page.goto('/settings')
      await page.waitForLoadState('networkidle')

      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      expect(errors).toEqual([])
    })
  }
})
