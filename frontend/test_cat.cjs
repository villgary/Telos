const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  // English context
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('http://192.168.1.58/login', { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'Admin123!');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(4000);

  // Assets page - check category options
  await page.goto('http://192.168.1.58/assets');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  // Click Add Asset
  const addBtn = page.locator('button:has-text("Add Asset")').first();
  await addBtn.click();
  await page.waitForTimeout(1000);

  // Get dropdown options for asset category
  const opts = await page.locator('.ant-select-dropdown .ant-select-item-option-content').allTextContents();
  console.log('Category options:', opts);

  // Check for Chinese vs English
  const hasChinese = opts.some(o => /[\u4e00-\u9fff]/.test(o));
  console.log('Has Chinese in options:', hasChinese ? 'YES (bug)' : 'NO (fixed)');

  await browser.close();
})();
