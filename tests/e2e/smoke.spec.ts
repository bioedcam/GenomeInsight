import { test, expect } from '@playwright/test'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

test.describe('Application smoke tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/')
    // The app should render without errors
    await expect(page).toHaveTitle(/GenomeInsight/)
  })

  test('health endpoint responds', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/health`)
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.status).toBe('ok')
  })
})
