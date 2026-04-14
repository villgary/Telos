import { test, expect } from '@playwright/test'

test('debug: check network requests when expanding group', async ({ page }) => {
  // Listen for API calls
  const apiCalls: string[] = []
  page.on('response', response => {
    if (response.url().includes('/assets') || response.url().includes('/asset-groups')) {
      apiCalls.push(`${response.request().method()} ${response.url()} -> ${response.status()}`)
    }
  })

  // Login
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle' })
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('http://192.168.1.9/', { timeout: 10000 })

  // Go to asset groups
  await page.goto('http://192.168.1.9/asset-groups')
  await page.waitForLoadState('networkidle')
  await page.waitForSelector('.ant-table-tbody .ant-table-row', { timeout: 15000 })

  console.log('API calls before expand:', apiCalls.length)

  // Find database row and get its data-record-key
  const rows = await page.locator('.ant-table-tbody .ant-table-row').all()
  for (const row of rows) {
    const text = (await row.textContent()) || ''
    if (text.includes('database')) {
      const key = await row.getAttribute('data-row-key')
      console.log(`Database row key: ${key}`)
      const dataExpanded = await row.getAttribute('aria-expanded')
      console.log(`Database row aria-expanded: ${dataExpanded}`)
    }
  }

  // Clear API calls and click expand
  apiCalls.length = 0
  const dbRow = page.locator('.ant-table-tbody .ant-table-row').filter({ hasText: 'database' }).first()
  await dbRow.locator('.ant-table-row-expand-icon').click()

  // Wait and collect API calls
  await page.waitForTimeout(3000)
  console.log(`API calls after expand: ${apiCalls.length}`)
  for (const call of apiCalls) {
    console.log('  ', call)
  }

  // Check expanded content
  const expandedRows = await page.locator('.ant-table-tbody .ant-table-expanded-row').all()
  console.log(`Expanded rows in DOM: ${expandedRows.length}`)
  for (const row of expandedRows) {
    const text = (await row.textContent()) || ''
    console.log('Expanded row:', text.replace(/\s+/g, ' ').trim())
  }

  // Also check data-row-key on expanded rows
  const expandedRowKeys = await page.locator('.ant-table-tbody .ant-table-expanded-row').evaluateAll(
    els => els.map(el => el.getAttribute('data-row-key'))
  )
  console.log('Expanded row keys:', expandedRowKeys)

  console.log('Debug test done')
})
