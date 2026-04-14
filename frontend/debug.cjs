const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if (msg.type() === 'error') errors.push('CON: ' + msg.text()); });

  await page.goto('http://192.168.1.9/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.locator('input[type="text"]').fill('admin');
  await page.locator('input[type="password"]').fill('Admin123!');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(3000);
  await page.goto('http://192.168.1.9/identity-threat', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  // Click Ontological Identity tab
  await page.locator('.ant-tabs-tab').filter({ hasText: 'Ontological Identity' }).click();
  await page.waitForTimeout(2000);
  
  const body = await page.locator('body').innerText();
  console.log('After clicking Ontological tab - body length:', body.length);
  console.log('Body (first 300):', body.slice(0, 300));
  console.log('Errors:', errors.map(e => e.slice(0, 150)));
  
  await browser.close();
})();
