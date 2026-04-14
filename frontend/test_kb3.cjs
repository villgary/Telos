const { chromium } = require('playwright');

(async () => {
  // Get token first
  const http = require('http');
  const { promisify } = require('util');
  
  function postForm(url, data) {
    return new Promise((resolve, reject) => {
      const urlObj = require('url').parse(url);
      const postData = Object.entries(data).map(([k,v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port,
        path: urlObj.path,
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': Buffer.byteLength(postData) }
      };
      const req = http.request(options, res => {
        let d = '';
        res.on('data', c => d += c);
        res.on('end', () => resolve(JSON.parse(d)));
      });
      req.on('error', reject);
      req.write(postData);
      req.end();
    });
  }
  
  const loginData = await postForm('http://192.168.1.9/api/v1/auth/login', { username: 'admin', password: 'Admin123!' });
  const token = loginData.access_token;
  console.log('Token obtained:', token ? 'YES' : 'NO');
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const apiCalls = [];
  const errors = [];
  page.on('response', r => {
    if (r.url().includes('/api/')) {
      apiCalls.push(`${r.request().method()} ${r.url()} -> ${r.status()}`);
    }
  });
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  
  // Set token in localStorage
  await page.goto('http://192.168.1.9/knowledge-base', { waitUntil: 'domcontentloaded' });
  await page.evaluate((t) => {
    localStorage.setItem('token', t);
  }, token);
  
  // Reload to pick up the token
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(5000);
  
  console.log('\n=== API Calls ===');
  apiCalls.forEach(c => console.log(c));
  
  console.log('\n=== Errors ===');
  errors.forEach(e => console.log(e));
  
  // Check state
  const listItems = await page.$$eval('.ant-list-item', els => els.length).catch(() => -1);
  const badgeCounts = await page.$$eval('.ant-badge-count', els => els.map(e => e.textContent)).catch(() => []);
  const statValues = await page.$$eval('.ant-statistic-content-value', els => els.map(e => e.textContent)).catch(() => []);
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 600));
  
  console.log('\n=== Rendered ===');
  console.log('List items:', listItems);
  console.log('Badge counts:', badgeCounts);
  console.log('Stat values:', statValues);
  console.log('Body:', bodyText);
  
  await browser.close();
})().catch(e => console.error('Fatal:', e.message));
