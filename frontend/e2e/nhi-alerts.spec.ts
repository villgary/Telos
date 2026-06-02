import { test, expect } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173'

test.beforeEach(async ({ page }) => {
  // Try to go to home — if session expired we'll be redirected to /login
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000) // Allow redirect to /login to complete if session expired
  // If redirected to login, log in as admin
  if (page.url().includes('/login')) {
    await page.locator('#username').fill('admin')
    await page.locator('#password').fill('Admin123!')
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/$/, { timeout: 30000 }).catch(() => {})
    await page.waitForLoadState('networkidle')
  }
})

test('NHI alerts tab loads and shows alerts table', async ({ page }) => {
  await page.goto(`${BASE}/nhi`)
  await expect(page.getByRole('heading', { name: /NHI/ })).toBeVisible()

  // Click the Alerts tab
  await page.getByRole('button', { name: /Alerts/ }).click()

  // The table is rendered (might be empty, but the table container exists)
  await expect(page.locator('.ant-table')).toBeVisible()
})

test('NHI alert type filter is present and selectable', async ({ page }) => {
  await page.goto(`${BASE}/nhi`)
  await page.getByRole('button', { name: /Alerts/ }).click()

  // The filter Select exists
  const filter = page.getByPlaceholder(/Filter by alert type|按告警类型筛选/)
  await expect(filter).toBeVisible()

  // Open the dropdown and pick an option
  await filter.click()
  await page.getByText(/Cross-asset spread|跨资产扩散/).click()

  // The selection chip should appear
  await expect(page.locator('.ant-select-selection-item')).toContainText(
    /Cross-asset spread|跨资产扩散/,
  )
})
