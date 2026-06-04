import { test, expect, Page } from '@playwright/test'

const BASE = process.env.BASE_URL || 'http://192.168.1.10'
const USERNAME = 'admin'
const PASSWORD = 'Admin123!'

async function login(page: Page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    localStorage.setItem('language', 'zh-CN')
    localStorage.setItem('i18nextLng', 'zh-CN')
  })
  await page.reload({ waitUntil: 'networkidle' })
  await page.locator('button[type="submit"]').waitFor({ timeout: 15000 })
  await page.locator('#username').fill(USERNAME)
  await page.locator('#password').fill(PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForFunction(
    () => document.querySelector('.ant-layout-sider') !== null ||
         document.querySelector('.ant-menu') !== null,
    { timeout: 30000 }
  ).catch(() => {})
}

test.describe('Cloud Connections', () => {
  test('user can navigate to the cloud connections page', async ({ page }) => {
    await login(page)
    await page.goto(BASE + '/ai-agents/connections', { waitUntil: 'networkidle' })
    // Title is rendered in the locale chosen at login
    await expect(page.getByText(/Cloud Connections|云连接/)).toBeVisible({ timeout: 15000 })
  })
})
