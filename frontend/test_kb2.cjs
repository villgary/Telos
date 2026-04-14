const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const errors = [];
  const apiCalls = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));
  page.on('response', r => {
    if (r.url().includes('/api/')) {
      apiCalls.push(`${r.request().method()} ${r.url()} -> ${r.status()}`);
    }
  });
  
  // Login
  console.log('Navigating to login...');
  await page.goto('http://192.168.1.9/', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);
  
  // Fill login form - find the actual inputs
  const usernameInput = page.locator('input').first();
  const passwordInput = page.locator('input[type="password"]').first();
  const loginBtn = page.locator('button').first();
  
  await usernameInput.fill('admin');
  await passwordInput.fill('Admin123!');
  await loginBtn.click();
  await page.waitForTimeout(3000);
  
  // Check login success - look for dashboard or logged-in state
  const currentUrl = page.url();
  console.log('After login URL:', currentUrl);
  const bodyAfterLogin = await page.evaluate(() => document.body.innerText.substring(0, 200));
  console.log('After login body:', bodyAfterLogin);
  
  // Navigate to KB
  await page.goto('http://192.168.1.9/knowledge-base', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(5000);
  
  console.log('\n=== API Calls ===');
  apiCalls.forEach(c => console.log(c));
  
  console.log('\n=== Errors ===');
  errors.forEach(e => console.log(e));
  
  // Check what's rendered
  const listItems = await page.$$eval('.ant-list-item', els => els.length).catch(() => -1);
  const statValues = await page.$$eval('.ant-statistic-content-value, .ant-statistic-content', els => els.map(e => e.textContent)).catch(() => []);
  const badgeCounts = await page.$$eval('.ant-badge-count', els => els.map(e => e.textContent)).catch(() => []);
  
  console.log('\n=== Rendered State ===');
  console.log('List items:', listItems);
  console.log('Stat values:', statValues);
  console.log('Badge counts:', badgeCounts);
  
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 800));
  console.log('\nBody text:', bodyText);
  
  await browser.close();
})().catch(e => console.error('Fatal:', e.message));
