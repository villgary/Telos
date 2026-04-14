const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push('PAGE ERROR: ' + err.message));

  // Login
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle', timeout: 60000 });
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'Admin@123');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/login', { timeout: 5000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 15000 });
  
  console.log('After login URL:', page.url());

  // Navigate to identity-threat
  await page.goto('http://192.168.1.9/identity-threat', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  
  // Check h4
  const h4 = await page.locator('h4').first();
  const visible = await h4.isVisible({ timeout: 5000 }).catch(() => false);
  console.log('h4 visible:', visible);
  if (visible) {
    console.log('h4 text:', await h4.textContent());
  }
  
  // Check page content
  const body = await page.locator('body').innerText();
  console.log('Body text (first 600):', body.slice(0, 600));
  
  if (errors.length > 0) {
    console.log('ERRORS:', JSON.stringify(errors.slice(0, 10)));
  }
  
  await browser.close();
})();
