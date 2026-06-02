import { test, expect } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173'

test.beforeEach(async ({ page }) => {
  // Login as admin
  await page.goto(`${BASE}/login`)
  await page.fill('input[name="username"]', 'admin')
  await page.fill('input[name="password"]', 'Admin123!')
  await page.click('button[type="submit"]')
  await page.waitForURL(/\/$/)
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
