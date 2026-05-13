import type { Page } from '@playwright/test'

/**
 * Wait until React has hydrated AppLayout. `networkidle` is unreliable for
 * this purpose because the dev server can return an empty `<div id="root">`
 * shell and no further requests follow, so the load state resolves before
 * mount. Once the page-level h1 is visible, AppLayout + the page component
 * have rendered and DOM-inspection assertions are safe to run.
 */
export async function waitForReactHydration(page: Page): Promise<void> {
  await page.locator('h1').first().waitFor({ state: 'visible' })
}
