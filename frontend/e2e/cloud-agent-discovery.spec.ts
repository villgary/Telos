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

test('Cloud Agent Discovery: page loads and shows the title', async ({ page }) => {
  await login(page)
  await page.goto(BASE + '/ai-agents/discovery', { waitUntil: 'networkidle' })
  await expect(page.getByText(/Cloud Agent Discovery|云端 Agent 发现/)).toBeVisible({ timeout: 15000 })
})

test('Cloud Agent Discovery: can add a source and see it in the audit log', async ({ page }) => {
  // Use a unique name per run so reruns don't collide
  const connName = `e2e-test-${Date.now()}`

  await login(page)
  await page.goto(BASE + '/ai-agents/discovery', { waitUntil: 'networkidle' })
  await expect(page.getByText(/Cloud Agent Discovery|云端 Agent 发现/)).toBeVisible({ timeout: 15000 })

  // Open the Add Source modal
  await page.getByRole('button', { name: /Add Source|新增来源/ }).click()
  await expect(page.getByText(/Add Cloud Agent Source|新增云端 Agent 来源/)).toBeVisible({ timeout: 5000 })

  // Fill the form
  await page.locator('input[id*="name" i]').first().fill(connName)
  // Provider is an antd Select — click to open, then click the Anthropic option
  await page.locator('.ant-select').first().click()
  await page.getByText(/Anthropic Console/, { exact: false }).first().click()
  // API key field is type=password
  await page.locator('input[type="password"]').first().fill('sk-e2e-test-key-not-real')

  // Submit
  await page.getByRole('button', { name: /^Add$|^新增$/ }).click()

  // The new source should appear in the table
  await expect(page.getByText(connName)).toBeVisible({ timeout: 10000 })

  // Open the audit drawer and verify a "Created" entry exists
  await page.getByRole('button', { name: /Audit Log|审计日志/ }).first().click()
  await expect(page.getByText(/Created|已创建/)).toBeVisible({ timeout: 5000 })
})
