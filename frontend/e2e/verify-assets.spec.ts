import { test, expect } from '@playwright/test'

test('assets page shows correct OS types and untested status', async ({ page }) => {
  // Login
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle' })
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('http://192.168.1.9/', { timeout: 10000 })
  console.log('Logged in')
  
  // Navigate to assets page
  await page.goto('http://192.168.1.9/assets')
  await page.waitForSelector('.ant-table-row', { timeout: 10000 })
  
  const rows = await page.locator('.ant-table-row').all()
  console.log(`Found ${rows.length} asset rows`)
  
  for (const row of rows) {
    const text = await row.textContent()
    console.log('Row:', text?.replace(/\s+/g, ' ').trim())
  }
  
  // Verify correct OS types
  for (const row of rows) {
    const text = (await row.textContent()) || ''
    if (text.includes('192.168.1.52')) {
      expect(text, 'Windows asset should show Windows').toMatch(/windows/i)
      expect(text, 'Should show untested status').toMatch(/untested/i)
    }
    if (text.includes('192.168.1.15') || text.includes('192.168.1.18')) {
      expect(text, 'Linux asset should show Linux').toMatch(/linux/i)
      expect(text, 'Should show untested status').toMatch(/untested/i)
    }
  }
  console.log('All assertions passed!')
})
