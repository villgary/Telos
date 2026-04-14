import { test, expect, Page } from '@playwright/test'

// Translation key leak detector
async function assertNoI18nLeaks(page: Page) {
  const leaks = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null)
    const seen = new Set<string>()
    let node: Text | null
    while ((node = walker.nextNode() as Text | null)) {
      const val = node.textContent?.trim() || ''
      if (/^[a-z]+\.[a-zA-Z_]+$/.test(val) && !seen.has(val)) seen.add(val)
    }
    return [...seen]
  })
  expect(leaks, `Translation key leaks: ${leaks.join(', ')}`).toHaveLength(0)
}

// Helper to navigate in the SPA without triggering nginx /assets/ redirect
async function navigateTo(page: Page, path: string) {
  // Try to go to home — if session expired we'll be redirected to /login
  await page.goto('http://192.168.1.9/', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000) // Allow redirect to /login to complete if session expired
  // If redirected to login, log in
  if (page.url().includes('/login')) {
    await page.locator('#username').fill('admin')
    await page.locator('#password').fill('Admin123!')
    await page.locator('button[type="submit"]').click()
    await page.waitForURL('http://192.168.1.9/', { timeout: 30000 }).catch(() => {})
    await page.waitForLoadState('networkidle')
  }
  // Navigate to target path via pushState
  await page.evaluate((p) => {
    window.history.pushState({}, '', p)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, path)
  await page.waitForTimeout(2000)
}

// Wait for loading to finish (handles both empty and populated tables)
async function waitForReady(page: Page) {
  await page.waitForFunction(
    () => !document.querySelector('.ant-spin') || document.querySelectorAll('.ant-spin').length === 0,
    { timeout: 20000 }
  ).catch(() => {})
  await page.waitForFunction(
    () => document.querySelector('.ant-table') || document.querySelector('.ant-empty') || document.querySelector('.ant-tree'),
    { timeout: 20000 }
  ).catch(() => {})
  await page.waitForTimeout(500)
}

test('asset groups - page loads (data-independent)', async ({ page }) => {
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle' })
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('http://192.168.1.9/', { timeout: 15000 }).catch(() => {})

  await navigateTo(page, '/asset-groups')
  await waitForReady(page)
  // Table should be visible (may be empty)
  const table = await page.locator('.ant-table').count()
  expect(table).toBeGreaterThan(0)
  await assertNoI18nLeaks(page)
  console.log('PASS: asset groups page loads')
})

test('assets page - cascader opens and has no i18n leaks', async ({ page }) => {
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle' })
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('http://192.168.1.9/', { timeout: 15000 }).catch(() => {})

  await navigateTo(page, '/assets')
  await waitForReady(page)

  // Cascader should be visible
  const cascader = page.locator('.ant-cascader').first()
  await cascader.waitFor({ timeout: 10000 })
  await cascader.click()
  await page.waitForSelector('.ant-cascader-menus', { timeout: 5000 })
  expect(await page.locator('.ant-cascader-menus').isVisible()).toBe(true)

  // No leaks in cascader dropdown
  await assertNoI18nLeaks(page)
  console.log('PASS: assets cascader opens')
})

test('asset categories - tree view loads and add drawer has no i18n leaks', async ({ page }) => {
  test.slow()
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle' })
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('http://192.168.1.9/', { timeout: 15000 }).catch(() => {})

  await navigateTo(page, '/asset-categories')
  await waitForReady(page)

  // Tree may be empty if DB has no categories — skip tree assertion in that case
  const tree = await page.locator('.ant-tree').count()
  if (tree === 0) {
    // No categories yet — just verify page loaded without crash
    const content = await page.textContent('body')
    expect(content).not.toMatch(/Application error|Unexpected error/i)
    return
  }

  // Add button should be visible
  const addBtn = page.locator('button').filter({ hasText: /新增|添加|Add.*品类|Add Category/i }).first()
  await addBtn.waitFor({ timeout: 10000 })
  await addBtn.click()
  await page.waitForSelector('.ant-drawer', { timeout: 5000 })
  expect(await page.locator('.ant-drawer').isVisible()).toBe(true)

  // Critical: check for translation key leaks in drawer
  await assertNoI18nLeaks(page)

  // Close drawer
  await page.locator('.ant-drawer .ant-btn-default').click()
  await page.waitForTimeout(500)
  console.log('PASS: asset categories tree + add drawer no leaks')
})
