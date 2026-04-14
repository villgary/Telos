const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ locale: 'zh-CN' });
  const page = await context.newPage();

  // Set zh-CN + operator mode in localStorage
  await page.goto('http://192.168.1.58/login', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    localStorage.setItem('language', 'zh-CN');
    localStorage.setItem('i18nextLng', 'zh-CN');
    localStorage.setItem('viewMode', 'operator');
  });
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'Admin123!');
  await page.waitForTimeout(4000);

  const routes = [
    // Admin pages
    ['http://192.168.1.58/', ['仪表盘', '总资产数', 'AI 智能分析']],
    ['http://192.168.1.58/assets', ['添加资产', '资产编号', '主机名', 'IP']],
    ['http://192.168.1.58/knowledge-base', ['知识库', '浏览知识库', '安全问答']],
    ['http://192.168.1.58/asset-topology', ['资产拓扑', '攻击路径']],
    ['http://192.168.1.58/alerts', ['告警中心']],
    ['http://192.168.1.58/compliance', ['合规中心']],
    ['http://192.168.1.58/review', ['审查提醒']],
    ['http://192.168.1.58/credentials', ['凭据管理']],
    // Operator mode
    ['http://192.168.1.58/', ['运营操作台', '待处置']],
  ];

  let passed = 0, failed = 0;
  for (const [url, terms] of routes) {
    await page.goto(url);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const body = await page.textContent('body');
    for (const term of terms) {
      if (body.includes(term)) { passed++; }
      else { console.log(`FAIL: ${url} missing "${term}"`); failed++; }
    }
  }
  console.log(`\n${passed}/${passed+failed} zh-CN content checks passed`);
  await browser.close();
  process.exit(failed === 0 ? 0 : 1);
})();
