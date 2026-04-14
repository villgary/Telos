const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));
  page.on('response', r => {
    if (r.url().includes('/kb/')) {
      console.log('KB API:', r.url(), '->', r.status());
    }
  });
  
  await page.goto('http://192.168.1.9/login', { waitUntil: 'networkidle', timeout: 15000 });
  try {
    await page.fill('input[placeholder*="用户名"], input[name="username"]', 'admin');
    await page.fill('input[type="password"]', 'Admin123!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  } catch(e) {
    console.log('Login error:', e.message);
  }
  
  await page.goto('http://192.168.1.9/knowledge-base', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(4000);
  
  const title = await page.textContent('h4').catch(() => 'not found');
  const listItems = await page.$$eval('.ant-list-item', els => els.length).catch(() => -1);
  const badgeTexts = await page.$$eval('.ant-badge-count', els => els.map(e => e.textContent || e.innerText)).catch(() => []);
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 600));
  
  console.log('Page title h4:', title);
  console.log('List items found:', listItems);
  console.log('Badge counts:', badgeTexts);
  console.log('Body text:', bodyText);
  console.log('JS errors:', errors.slice(0, 5));
  
  await browser.close();
})().catch(e => console.error('Fatal:', e.message));
